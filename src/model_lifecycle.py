"""Model lifecycle: first-run download (with progress), engine preload,
release update check, and the GUI-side download progress dialog.

The preload and update-check functions are thread targets; they communicate
back to the GUI thread exclusively through the emit callables the app passes
in (Qt signal .emit), never by touching widgets.
"""

import logging

log = logging.getLogger("dictate.model_lifecycle")


def preload(engine, emit_dl_start, emit_dl_progress, emit_dl_done,
            emit_ready, emit_error):
    """Download the engine's model if not cached, then load it.
    Runs on a worker thread."""
    try:
        try:
            from . import first_run, paths
        except ImportError:
            import first_run
            import paths
        if not first_run.model_is_cached(engine.model_size,
                                         paths.models_dir()):
            emit_dl_start(engine.model_size)
            try:
                first_run.download_with_progress(
                    engine.model_size, paths.models_dir(),
                    emit_dl_progress)
            finally:
                emit_dl_done()
        engine.load()
        emit_ready(engine.active_device or "?")
    except Exception as ex:
        log.exception("model preload failed")
        emit_error(f"Model failed to load: {ex}")


def update_check(emit_update_available):
    """Throttled GitHub release check (max ~1 HTTP call/day), fail-silent.
    Runs on a worker thread."""
    try:
        try:
            from . import paths as _paths, update_check as _update_check, version
        except ImportError:
            import paths as _paths
            import update_check as _update_check
            import version
        upd = _update_check.check_github(
            "jasoisjaso/dictate", version.__version__,
            state_dir=_paths.app_data_dir())
        if upd:
            emit_update_available(upd.tag, upd.url)
    except Exception:
        log.debug("update check failed", exc_info=True)


class DownloadProgressUI:
    """First-run model-download dialog. All three handlers run on the GUI
    thread (connected to Qt signals by the app)."""

    def __init__(self):
        self._dialog = None

    def on_start(self, model_size: str):
        from PySide6.QtWidgets import QProgressDialog

        from .first_run import APPROX_SIZE
        size_hint = APPROX_SIZE.get(model_size, "")
        label = (f"Downloading the speech model ({model_size}"
                 + (f", about {size_hint}" if size_hint else "")
                 + ").\nThis happens once — after this Dictate works offline.")
        dlg = QProgressDialog(label, None, 0, 100)
        dlg.setWindowTitle("Dictate — first-time setup")
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setValue(0)
        dlg.show()
        self._dialog = dlg

    def on_progress(self, pct: int):
        if self._dialog is not None:
            self._dialog.setValue(pct)

    def on_done(self):
        if self._dialog is not None:
            self._dialog.close()
            self._dialog = None
