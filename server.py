"""Transcribe — local Whisper transcription server.

faster-whisper (CTranslate2) on CUDA, large-v3-turbo by default.
Single GPU worker thread; jobs persisted as JSON under ~/.cache/transcribe/data.
"""

import gc
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("TRANSCRIBE_DATA", Path.home() / ".cache/transcribe/data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG = shutil.which("ffmpeg") or str(Path.home() / ".local/bin/ffmpeg")

# id -> (model repo name, label)
MODELS = {
    "large-v3-turbo": "Turbo — best speed/accuracy balance (default)",
    "large-v3": "Large v3 — maximum accuracy, slower",
    "distil-large-v3": "Distil — fastest, English only",
    "small": "Small — low resource fallback",
}
DEFAULT_MODEL = "large-v3-turbo"

app = FastAPI(title="Transcribe")

jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()
work_q: queue.Queue[str] = queue.Queue()

_model = None
_model_name = None
_device = None


def _load_model(name: str):
    """Load (or switch) the whisper model. CUDA first, CPU int8 fallback."""
    global _model, _model_name, _device
    if _model is not None and _model_name == name:
        return _model
    from faster_whisper import WhisperModel

    if _model is not None:
        _model = None
        gc.collect()
    try:
        _model = WhisperModel(name, device="cuda", compute_type="int8_float16")
        _device = "cuda"
    except Exception as e:
        print(f"[transcribe] CUDA load failed ({e}); falling back to CPU int8")
        _model = WhisperModel(name, device="cpu", compute_type="int8")
        _device = "cpu"
    _model_name = name
    return _model


def _save_job(job: dict):
    tmp = DATA_DIR / f".{job['id']}.tmp"
    tmp.write_text(json.dumps(job, ensure_ascii=False))
    tmp.replace(DATA_DIR / f"{job['id']}.json")


def _load_jobs():
    for p in sorted(DATA_DIR.glob("*.json")):
        try:
            job = json.loads(p.read_text())
            if job.get("status") in ("queued", "processing"):
                job["status"] = "error"
                job["error"] = "interrupted by server restart"
            jobs[job["id"]] = job
        except Exception:
            continue


def _to_wav(src: Path) -> Path:
    """Normalise any audio/video input to 16 kHz mono wav via ffmpeg."""
    out = src.with_suffix(".16k.wav")
    r = subprocess.run(
        [FFMPEG, "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
         "-f", "wav", str(out)],
        capture_output=True, text=True, timeout=1800,
    )
    if r.returncode != 0 or not out.exists() or out.stat().st_size < 100:
        tail = (r.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError("ffmpeg could not decode this file: " + " | ".join(tail))
    return out


def _worker():
    while True:
        job_id = work_q.get()
        with jobs_lock:
            job = jobs.get(job_id)
        if job is None:
            continue
        src = Path(job["upload_path"])
        wav = None
        try:
            job["status"] = "processing"
            job["started"] = time.time()
            _save_job(job)

            wav = _to_wav(src)
            model = _load_model(job["model"])
            job["device"] = _device
            _save_job(job)

            segments_gen, info = model.transcribe(
                str(wav),
                language=job["language"] or None,
                task=job["task"],
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                condition_on_previous_text=False,
                beam_size=5,
            )
            job["detected_language"] = info.language
            job["language_probability"] = round(info.language_probability, 3)
            job["duration"] = round(info.duration, 2)

            segs = []
            for seg in segments_gen:
                segs.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip(),
                })
                if info.duration:
                    job["progress"] = min(99, int(seg.end / info.duration * 100))
                # persist progress cheaply, every ~10 segments
                if len(segs) % 10 == 0:
                    _save_job(job)

            job["segments"] = segs
            job["text"] = "\n".join(s["text"] for s in segs)
            job["progress"] = 100
            job["status"] = "done"
            job["finished"] = time.time()
            job["elapsed"] = round(job["finished"] - job["started"], 1)
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
        finally:
            _save_job(job)
            for p in (src, wav):
                try:
                    if p and Path(p).exists():
                        Path(p).unlink()
                except OSError:
                    pass
            work_q.task_done()


threading.Thread(target=_worker, daemon=True).start()
_load_jobs()


def _fmt_ts(t: float, vtt: bool = False) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    ms = int((s - int(s)) * 1000)
    sep = "." if vtt else ","
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{ms:03d}"


def _srt(segs) -> str:
    return "\n".join(
        f"{i}\n{_fmt_ts(s['start'])} --> {_fmt_ts(s['end'])}\n{s['text']}\n"
        for i, s in enumerate(segs, 1)
    )


def _vtt(segs) -> str:
    body = "\n".join(
        f"{_fmt_ts(s['start'], vtt=True)} --> {_fmt_ts(s['end'], vtt=True)}\n{s['text']}\n"
        for s in segs
    )
    return "WEBVTT\n\n" + body


@app.get("/", response_class=HTMLResponse)
def index():
    return (APP_DIR / "static" / "index.html").read_text()


@app.get("/api/status")
def status():
    return {
        "models": MODELS,
        "default_model": DEFAULT_MODEL,
        "loaded_model": _model_name,
        "device": _device,
        "queue_length": work_q.qsize(),
    }


@app.post("/api/transcribe")
async def create_job(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_MODEL),
    language: str = Form(""),
    task: str = Form("transcribe"),
):
    if model not in MODELS:
        raise HTTPException(400, f"unknown model {model!r}")
    if task not in ("transcribe", "translate"):
        raise HTTPException(400, "task must be transcribe or translate")

    job_id = uuid.uuid4().hex[:12]
    suffix = Path(file.filename or "upload").suffix or ".bin"
    dest = UPLOAD_DIR / f"{job_id}{suffix}"
    size = 0
    with dest.open("wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            f.write(chunk)
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "empty file")

    job = {
        "id": job_id,
        "filename": file.filename or "recording",
        "size": size,
        "model": model,
        "language": language.strip().lower(),
        "task": task,
        "status": "queued",
        "progress": 0,
        "created": time.time(),
        "upload_path": str(dest),
    }
    with jobs_lock:
        jobs[job_id] = job
    _save_job(job)
    work_q.put(job_id)
    return {"id": job_id}


@app.get("/api/jobs")
def list_jobs():
    with jobs_lock:
        out = [
            {k: v for k, v in j.items() if k not in ("segments", "text", "upload_path")}
            for j in jobs.values()
        ]
    return sorted(out, key=lambda j: j["created"], reverse=True)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "no such job")
    return {k: v for k, v in job.items() if k != "upload_path"}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    with jobs_lock:
        job = jobs.pop(job_id, None)
    if not job:
        raise HTTPException(404, "no such job")
    (DATA_DIR / f"{job_id}.json").unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str, fmt: str = "txt"):
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "job not finished")
    stem = Path(job["filename"]).stem or "transcript"
    segs = job["segments"]
    if fmt == "txt":
        content, mime = job["text"], "text/plain"
    elif fmt == "srt":
        content, mime = _srt(segs), "application/x-subrip"
    elif fmt == "vtt":
        content, mime = _vtt(segs), "text/vtt"
    elif fmt == "json":
        content = json.dumps(
            {"filename": job["filename"], "language": job.get("detected_language"),
             "duration": job.get("duration"), "segments": segs},
            ensure_ascii=False, indent=2)
        mime = "application/json"
    else:
        raise HTTPException(400, "fmt must be txt, srt, vtt or json")
    return PlainTextResponse(
        content, media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{stem}.{fmt}"'},
    )
