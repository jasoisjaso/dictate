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


def test_corrupt_config_does_not_crash_and_is_salvaged(tmp_path, monkeypatch):
    """The real-world bug: an older build wrote an unquoted multi-word key
    ('Purchase Order = "PO"'), which is invalid TOML and crashed startup.
    load() must now recover the valid sections instead of raising."""
    _isolate(tmp_path, monkeypatch)
    (tmp_path / "settings.toml").write_text(
        "[whisper]\n"
        'model_size = "auto"\n'
        'language = "en"\n\n'
        "[hotkeys]\n"
        'mode = "push_to_talk"\n\n'
        "[dictionary]\n"
        'Purchase Order = "PO"\n',      # <-- invalid: unquoted key with a space
        encoding="utf-8")
    cfg = config.load(defaults={})       # must NOT raise
    assert cfg["whisper"]["model_size"] == "auto"
    assert cfg["hotkeys"]["mode"] == "push_to_talk"
    # the corrupt file is backed up, not left in place to crash next boot
    baks = list(tmp_path.glob("settings.toml.corrupt-*.bak"))
    assert len(baks) == 1


def test_corrupt_config_keeps_good_keys_in_same_section(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    (tmp_path / "settings.toml").write_text(
        "[dictionary]\n"
        'woolies = "Woolworths"\n'        # good
        'Purchase Order = "PO"\n'         # bad
        'helloacrylic = "Hello Acrylic"\n',  # good
        encoding="utf-8")
    cfg = config.load(defaults={})
    d = cfg.get("dictionary", {})
    assert d.get("woolies") == "Woolworths"
    assert d.get("helloacrylic") == "Hello Acrylic"
    assert "Purchase Order" not in d
