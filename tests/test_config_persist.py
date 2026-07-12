"""Persistence regression tests for the "saved a setting, relaunched, gone" bug.

The custom filler list (and every GUI setting) must survive a save->reload
round-trip, and saving from the GUI must NOT wipe keys the user only set by
hand-editing the TOML (ollama_*, app_profiles, ...).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import config  # noqa: E402
import paths as _paths  # noqa: E402


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(_paths, "config_path",
                        lambda: str(tmp_path / "settings.toml"))
    monkeypatch.setattr(config.paths, "config_path",
                        lambda: str(tmp_path / "settings.toml"))


def test_custom_fillers_round_trip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    config.save({"cleanup": {"remove_fillers": True,
                             "custom_fillers": ["like", "you know", "basically"]}})
    loaded = config.load(defaults={})
    assert loaded["cleanup"]["custom_fillers"] == ["like", "you know", "basically"]
    assert loaded["cleanup"]["remove_fillers"] is True


def test_empty_custom_fillers_round_trip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    config.save({"cleanup": {"custom_fillers": []}})
    assert config.load(defaults={})["cleanup"]["custom_fillers"] == []


def test_save_does_not_wipe_handedited_keys(tmp_path, monkeypatch):
    """This is the real hardening: a GUI save that only knows about a few keys
    must merge, not clobber, so ollama settings + app_profiles stay put."""
    _isolate(tmp_path, monkeypatch)
    # user hand-edits their TOML with power-user keys the GUI never touches
    (tmp_path / "settings.toml").write_text(
        "[cleanup]\n"
        'ollama_model = "hermes4"\n'
        "ollama_polish = true\n"
        "\n"
        "[app_profiles.notes]\n"
        'match = ["Obsidian.exe"]\n',
        encoding="utf-8")
    # then opens Settings and hits Save, which only carries the fillers/checkbox
    config.save({"cleanup": {"remove_fillers": False,
                             "custom_fillers": ["um actually"]}})
    loaded = config.load(defaults={})
    # new values applied
    assert loaded["cleanup"]["remove_fillers"] is False
    assert loaded["cleanup"]["custom_fillers"] == ["um actually"]
    # hand-edited values SURVIVED (the bug would have wiped these)
    assert loaded["cleanup"]["ollama_model"] == "hermes4"
    assert loaded["cleanup"]["ollama_polish"] is True
    assert loaded["app_profiles"]["notes"]["match"] == ["Obsidian.exe"]


def test_quotes_and_special_chars_survive(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    config.save({"dictionary": {"say this": 'the "big" boss\\co'}})
    assert config.load(defaults={})["dictionary"]["say this"] == 'the "big" boss\\co'
