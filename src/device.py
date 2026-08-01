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


def choose_engine(engine_cfg: str, tier: Tier, language: str) -> str:
    """Which transcription engine to use — pure, table-tested.

    engine_cfg: the [engine] engine setting ("auto" | "whisper" | "parakeet";
    anything unknown is treated as auto). language: the RAW [whisper]
    language setting, so synthetic modes ("auto"/"multi"/"bs2en"/"en2bs")
    correctly count as unsupported — they all depend on bs recognition.

    Rules, in order (docs/parakeet-engine.md §3.3):
      1. Explicit "whisper" always wins.
      2. Explicit "parakeet" wins for its 25 languages; an unsupported
         language forces Whisper anyway (the UI shows why) — never a
         silent wrong-language result.
      3. auto: CPU tier + supported language -> parakeet (10-30x realtime
         beats Whisper small's 2-4x). CUDA tier -> whisper (large-v3-turbo
         with prompts + dictionary biasing is already excellent there).
    """
    try:
        from .engine_parakeet import PARAKEET_LANGS
    except ImportError:
        from engine_parakeet import PARAKEET_LANGS
    supported = language in PARAKEET_LANGS
    cfg = str(engine_cfg or "auto").strip().lower()
    if cfg == "whisper":
        return "whisper"
    if cfg == "parakeet":
        return "parakeet" if supported else "whisper"
    # auto (and anything unrecognised)
    if tier.device != "cuda" and supported:
        return "parakeet"
    return "whisper"


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


def streaming_ok(tier: Tier, engine: str = "whisper") -> bool:
    """Chunked while-you-talk transcription.

    Parakeet: always fine — 10-30x realtime on plain CPUs means a 14s chunk
    decodes in well under a second; commits can't pile up.
    Whisper GPU: always fine — chunk commits take a fraction of realtime.
    Whisper CPU: only worth it when the machine has real parallel headroom
    AND a model small enough that a 14s chunk transcribes in well under 14s;
    otherwise commits pile up behind each other and stall the final result.
    """
    if engine == "parakeet":
        return True
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


def ollama_pick_translate_model(endpoint: str = "http://127.0.0.1:11434",
                                timeout: float = 0.8) -> "str | None":
    """Best installed Ollama model for the TRANSLATION pass, or None.

    Unlike polish (where the user's preferred big model is fine because it
    rarely fires), translation sits directly in the time-to-text path of
    every Bosnian take, so fast-when-warm wins. Measured 2026-07-28
    (4060 Ti 16GB): qwen2.5:3b mistranslates content words (skladiste ->
    "archive", radio -> "went"); dolphin3:8b got the same sentence right
    and evals in 1-3s warm (~50s cold load, prewarmed at startup), so it
    leads. The tiny models stay as fallbacks for low-VRAM machines.
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
    for cand in ("dolphin3:8b", "qwen2.5:3b", "llama3.2:3b", "llama3.2:1b",
                 "gemma2:2b", "phi3.5:3.8b", "phi3.5", "llama3.2",
                 "qwen2.5:7b", "qwen2.5", "hermes4"):
        if cand in names:
            return cand
        base_match = [n for n in names if n.split(":")[0] == cand]
        if base_match:
            return base_match[0]
    return names[0]


def ollama_pick_bs_translate_model(endpoint: str = "http://127.0.0.1:11434",
                                   timeout: float = 0.8) -> "str | None":
    """Best installed Ollama model for translating INTO Bosnian.

    The small models that are perfect for bs->en butcher Bosnian output
    (broken words, ekavian drift). Measured 2026-07-28 (4060 Ti 16GB,
    slow disk): gpt-oss:20b writes the best Bosnian but its 13GB cold
    load took 224-400s and evicts whisper from VRAM on 16GB cards --
    every first take times out, the feature looks dead. hermes4:14b
    writes correct ijekavian ("Bit cu kod kuce...") and doubles as the
    default polish model, so in a normal session it is ALREADY resident
    in Ollama: near-zero marginal cost. qwen3:14b and dolphin3:8b both
    butcher Bosnian (enclitic-first word order, Cyrillic bleed). A
    Bosnian speaker instantly spots bad Bosnian, so quality-capable +
    actually-loadable order.
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
    for cand in ("hermes4:14b", "hermes4", "cogito:14b", "gpt-oss:20b",
                 "gpt-oss", "qwen3:14b", "qwen2.5:7b", "dolphin3:8b"):
        if cand in names:
            return cand
        base_match = [n for n in names if n.split(":")[0] == cand]
        if base_match:
            return base_match[0]
    return names[0]
