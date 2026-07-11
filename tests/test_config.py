import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import paths


def test_appdir_is_absolute_and_named():
    p = paths.app_data_dir()
    assert os.path.isabs(p)
    assert p.rstrip("/\\").endswith("TranscribeDictate")


def test_models_dir_under_appdir():
    assert paths.models_dir().startswith(paths.app_data_dir())


import config as cfgmod


def test_deep_merge_overrides_leaf(tmp_path, monkeypatch):
    monkeypatch.setattr(cfgmod.paths, "config_path",
                        lambda: str(tmp_path / "settings.toml"))
    (tmp_path / "settings.toml").write_text('[whisper]\nlanguage = "de"\n')
    merged = cfgmod.load(defaults={"whisper": {"language": "en", "beam_size": 5}})
    assert merged["whisper"]["language"] == "de"   # user wins
    assert merged["whisper"]["beam_size"] == 5      # default preserved


def test_save_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cfgmod.paths, "config_path",
                        lambda: str(tmp_path / "s.toml"))
    cfgmod.save({"hotkeys": {"mode": "toggle", "toggle_key": "f9"}})
    back = cfgmod.load(defaults={"hotkeys": {"mode": "push_to_talk"}})
    assert back["hotkeys"]["mode"] == "toggle"
