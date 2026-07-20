"""Hardware detection + model/compute tiering for faster-whisper.

choose_tier() is pure (testable). detect() probes the real machine and
delegates to choose_tier(). VRAM is read via nvidia-smi (no extra deps);
CUDA availability via ctranslate2 when present. AMD GPUs are detected via
WMIC so we can show an honest message instead of silently falling back.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass

log = logging.getLogger("dictate.device")


@dataclass
class Tier:
    device: str
    compute_type: str
    model_size: str
    amd_gpu: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def choose_tier(cuda: bool, vram_gb: float) -> Tier:
    """Map detected hardware to a safe (device, compute, model) combo.
    Thresholds leave headroom for CTranslate2 activations + the OS/desktop
    (a '4 GB' Windows card realistically has ~3.2-3.5 GB free)."""
    if not cuda:
        # CPU: int8 only. small is the accuracy/speed sweet spot on modern
        # multicore; the GUI offers distil-large-v3 for English speakers who
        # want more accuracy, but auto keeps multilingual defaults.
        return Tier("cpu", "int8", "small")
    if vram_gb >= 6.0:
        return Tier("cuda", "float16", "large-v3-turbo")
    if vram_gb >= 4.5:
        return Tier("cuda", "int8_float16", "large-v3-turbo")
    if vram_gb >= 3.0:
        return Tier("cuda", "int8_float16", "small")
    return Tier("cuda", "int8_float16", "base")


def _cuda_available() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception as ex:
        log.debug("ctranslate2 cuda probe failed: %s", ex)
        return False


def _vram_gb() -> float:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return 0.0
    try:
        out = subprocess.run(
            [exe, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        mibs = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
        return max(mibs) / 1024.0 if mibs else 0.0
    except Exception as ex:
        log.debug("nvidia-smi vram probe failed: %s", ex)
        return 0.0


def _amd_gpu_present() -> bool:
    """Check for AMD GPU via WMIC on Windows. Returns False on non-Windows."""
    exe = shutil.which("wmic")
    if not exe:
        return False
    try:
        out = subprocess.run(
            [exe, "path", "win32_VideoController", "get", "name"],
            capture_output=True, text=True, timeout=5)
        text = out.stdout.upper()
        return "AMD" in text or "RADEON" in text
    except Exception as ex:
        log.debug("AMD GPU probe failed: %s", ex)
        return False


def detect() -> Tier:
    cuda = _cuda_available()
    vram = _vram_gb() if cuda else 0.0
    tier = choose_tier(cuda, vram)
    amd = _amd_gpu_present() if not cuda else False
    if amd:
        log.info("AMD GPU detected — using CPU (DirectML support planned)")
        tier.amd_gpu = True
    log.info("auto device: cuda=%s vram=%.1fGB amd=%s -> %s",
             cuda, vram, amd, tier.as_dict())
    return tier


# ---- per-PC feature gating -------------------------------------------------
# The smart extras (streaming commits, live preview, Ollama polish) each cost
# compute. They must switch OFF automatically on machines that can't afford
# them: the app has to stay usable on a 2-core laptop with no GPU, just with
# fewer luxuries. All checks are cheap and cached by the caller.

def _cpu_cores() -> int:
    import os
    return os.cpu_count() or 2


def streaming_ok(tier: Tier) -> bool:
    """Chunked while-you-talk transcription.

    GPU: always fine — chunk commits take a fraction of realtime.
    CPU: only worth it when the machine has real parallel headroom AND a
    model small enough that a 14s chunk transcribes in well under 14s;
    otherwise commits pile up behind each other and stall the final result.
    """
    if tier.device == "cuda":
        return True
    return _cpu_cores() >= 8 and tier.model_size in ("tiny", "base", "small")


def preview_ok(tier: Tier) -> bool:
    """Live preview re-transcribes the tail every second — GPU only."""
    return tier.device == "cuda"


def ollama_ok(endpoint: str = "http://127.0.0.1:11434",
              timeout: float = 0.8) -> bool:
    """True if a local Ollama server is answering. This is a reachability
    probe, not a benchmark: if Ollama runs at all the user chose to install
    it, and the polish path stays fail-open (a slow reply just gets skipped
    by the polish timeout)."""
    import urllib.request
    try:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/api/tags",
                                    timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def ollama_pick_model(preferred: str,
                      endpoint: str = "http://127.0.0.1:11434",
                      timeout: float = 0.8) -> "str | None":
    """Best installed Ollama model for the polish pass, or None.

    Prefers the configured model if installed; otherwise falls back to any
    installed small instruct model. Polish is latency-sensitive (adds directly
    to time-to-text), so smaller is better.
    """
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/api/tags",
                                    timeout=timeout) as r:
            names = [m.get("name", "") for m in
                     json.loads(r.read()).get("models", [])]
    except Exception:
        return None
    if not names:
        return None
    base = {n.split(":")[0]: n for n in names}
    if preferred in names or preferred in base:
        return base.get(preferred, preferred)
    for cand in ("llama3.2", "qwen2.5", "gemma2", "phi3", "mistral",
                 "hermes4", "llama3.1", "llama3"):
        if cand in base:
            return base[cand]
    return names[0]
