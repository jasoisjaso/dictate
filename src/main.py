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
    from . import paths
    log_file = paths.log_path()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return log_file


def main():
    log_file = _setup_logging()
    log = logging.getLogger("dictate")
    log.info("=== Dictate starting (log: %s) ===", log_file)

    # Must happen before any faster_whisper / ctranslate2 import.
    from .win32_input import configure_cuda_dll_search_paths
    configure_cuda_dll_search_paths()

    from . import config as config_mod, paths
    cfg = config_mod.load()
    first_run = not os.path.exists(paths.config_path())

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
    tray_app = DictationTrayApp(cfg, app, first_run=first_run)  # noqa: F841
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
