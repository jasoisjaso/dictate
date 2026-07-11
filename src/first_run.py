"""First-run helper: pre-download the Whisper model with progress reporting,
so new users see a progress bar instead of a frozen tray icon."""

import logging

log = logging.getLogger("dictate.first_run")

APPROX_SIZE = {
    "tiny": "75 MB", "base": "150 MB", "small": "500 MB",
    "medium": "1.5 GB", "distil-large-v3": "1.5 GB",
    "large-v3-turbo": "1.6 GB", "large-v3": "3 GB",
}


def model_is_cached(model_size: str, cache_dir: str) -> bool:
    try:
        from faster_whisper.utils import download_model
        download_model(model_size, local_files_only=True, cache_dir=cache_dir)
        return True
    except Exception:
        return False


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
