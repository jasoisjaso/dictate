import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import paths


def test_not_portable_by_default():
    importlib.reload(paths)
    assert paths.is_portable() is False
    assert "Data" not in paths.app_data_dir()


def test_portable_marker_switches_to_data_dir(monkeypatch, tmp_path):
    (tmp_path / paths.PORTABLE_MARKER).write_text("")
    monkeypatch.setattr(paths, "install_root", lambda: str(tmp_path))
    assert paths.is_portable() is True
    assert paths.app_data_dir() == str(tmp_path / "Data")
    assert paths.models_dir() == str(tmp_path / "Data" / "models")
    assert paths.config_path().startswith(str(tmp_path / "Data"))
