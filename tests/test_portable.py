import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import paths


def test_not_portable_by_default():
    importlib.reload(paths)
    assert paths.is_portable() is False
    # the data dir must not be the portable Data/ folder next to the app.
    # NOTE: substring checks are wrong here — Windows paths legitimately
    # contain "AppData", which contains "Data".
    d = paths.app_data_dir()
    assert os.path.basename(d) != "Data"
    assert d != os.path.join(paths.install_root(), "Data")


def test_portable_marker_switches_to_data_dir(monkeypatch, tmp_path):
    (tmp_path / paths.PORTABLE_MARKER).write_text("")
    monkeypatch.setattr(paths, "install_root", lambda: str(tmp_path))
    assert paths.is_portable() is True
    assert paths.app_data_dir() == str(tmp_path / "Data")
    assert paths.models_dir() == str(tmp_path / "Data" / "models")
    assert paths.config_path().startswith(str(tmp_path / "Data"))
