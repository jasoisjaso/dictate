"""Entry point. Run from the repo root:  python -m src.main

DLL paths must be registered before faster_whisper/ctranslate2 are imported,
which is why this file touches win32_input first and defers everything else.
"""

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _setup_logging():
    log_dir = Path(os.environ.get("LOCALAPPDATA", ROOT)) / "TranscribeDictate"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "dictate.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return log_dir / "dictate.log"


def _load_config() -> dict:
    cfg_path = ROOT / "config" / "settings.toml"
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib
    with cfg_path.open("rb") as f:
        return tomllib.load(f)


def main():
    log_file = _setup_logging()
    log = logging.getLogger("dictate")
    log.info("=== Dictate starting (log: %s) ===", log_file)

    # Must happen before any faster_whisper / ctranslate2 import.
    from .win32_input import configure_cuda_dll_search_paths
    configure_cuda_dll_search_paths()

    cfg = _load_config()

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Dictate")

    lock = QLockFile(str(Path(os.environ.get("TEMP", "/tmp")) / "transcribe-dictate.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        log.error("another instance is already running — exiting")
        sys.exit(1)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        log.error("no system tray available")
        sys.exit(1)

    from .ui import DictationTrayApp
    tray_app = DictationTrayApp(cfg, app)  # noqa: F841  (owns the tray icon)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
