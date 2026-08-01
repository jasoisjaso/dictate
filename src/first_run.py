"""First-run helper: pre-download the Whisper model with progress reporting,
so new users see a progress bar instead of a frozen tray icon."""

import logging

log = logging.getLogger("dictate.first_run")

APPROX_SIZE = {
    "tiny": "75 MB", "base": "150 MB", "small": "500 MB",
    "medium": "1.5 GB", "distil-large-v3": "1.5 GB",
    "large-v3-turbo": "1.6 GB", "large-v3": "3 GB",
    "parakeet-tdt-0.6b-v3": "640 MB",
}


def model_is_cached(model_size: str, cache_dir: str) -> bool:
    try:
        from faster_whisper.utils import download_model
        download_model(model_size, local_files_only=True, cache_dir=cache_dir)
        return True
    except Exception:
        return False


# ---- Parakeet (sherpa-onnx) ------------------------------------------------
# Same lazy-download policy as the Whisper models, same progress-callback
# machinery, same cache dir — just a flat folder instead of HF hub layout so
# portable sticks can copy it as-is.

def parakeet_is_cached(cache_dir: str, override_dir: str = "") -> bool:
    try:
        from . import engine_parakeet as _pk
    except ImportError:
        import engine_parakeet as _pk
    d = _pk.model_dir(cache_dir, override_dir)
    return _pk.resolve_model_files(d) is not None


def download_parakeet_with_progress(cache_dir: str, progress_cb):
    """Download the int8 ONNX export (~640 MB). progress_cb(percent: int).
    Raises on failure — caller handles it (and the resume support in
    huggingface_hub means a retry picks up where it stopped)."""
    import shutil

    try:
        from . import engine_parakeet as _pk
    except ImportError:
        import engine_parakeet as _pk
    # ~700 MB free-disk pre-check so a full disk fails BEFORE a half-hour
    # download instead of at file 3 of 4.
    try:
        free = shutil.disk_usage(cache_dir).free
    except OSError:
        free = None
    if free is not None and free < 700 * 1024 * 1024:
        raise RuntimeError(
            "Not enough disk space for the Parakeet model — it needs about "
            f"700 MB free, this drive has {free // (1024 * 1024)} MB.")

    import huggingface_hub
    from tqdm.std import tqdm as _std_tqdm

    class _CbTqdm(_std_tqdm):
        def update(self, n=1):
            super().update(n)
            if self.total:
                progress_cb(min(99, int(self.n / self.total * 100)))

    dest = _pk.model_dir(cache_dir)
    log.info("downloading %s (~640 MB) to %s", _pk.HF_REPO, dest)
    huggingface_hub.snapshot_download(
        _pk.HF_REPO,
        local_dir=dest,
        allow_patterns=["*.onnx", "tokens.txt"],
        tqdm_class=_CbTqdm,
    )
    progress_cb(100)


def download_with_progress(model_size: str, cache_dir: str, progress_cb):
    """Download the CTranslate2 model repo. progress_cb(percent: int) gets
    0-100 based on completed files (byte-level detail isn't worth the
    complexity). Raises on network failure — caller handles it."""
    from faster_whisper.utils import _MODELS  # name -> HF repo id
    import huggingface_hub
    from tqdm.std import tqdm as _std_tqdm

    repo_id = _MODELS.get(model_size, model_size)

    class _CbTqdm(_std_tqdm):
        def update(self, n=1):
            super().update(n)
            if self.total:
                progress_cb(min(99, int(self.n / self.total * 100)))

    log.info("downloading %s (%s) to %s", repo_id,
             APPROX_SIZE.get(model_size, "?"), cache_dir)
    huggingface_hub.snapshot_download(
        repo_id,
        cache_dir=cache_dir,
        allow_patterns=["config.json", "preprocessor_config.json",
                        "model.bin", "tokenizer.json", "vocabulary.*"],
        tqdm_class=_CbTqdm,
    )
    progress_cb(100)
