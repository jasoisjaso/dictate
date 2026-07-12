import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import appcontext

PROFILES = {
    "terminal": {
        "match": ["WindowsTerminal.exe", "powershell.exe", "cmd.exe", "Code.exe"],
        "verbatim": True,
    },
    "chat": {
        "match": ["Discord.exe", "Slack.exe", "Teams.exe"],
        "casing": "lower_first",
        "tone": "casual",
    },
    "email": {
        "match": ["OUTLOOK.EXE", "Thunderbird.exe"],
        "tone": "professional",
    },
}


def test_exact_exe_match_case_insensitive():
    p = appcontext.resolve_profile("windowsterminal.exe", PROFILES)
    assert p["verbatim"] is True


def test_unknown_exe_gets_default_empty_profile():
    p = appcontext.resolve_profile("notepad.exe", PROFILES)
    assert p == {}


def test_none_exe_gets_default():
    assert appcontext.resolve_profile(None, PROFILES) == {}


def test_wildcard_suffix_match():
    profiles = {"jet": {"match": ["idea*.exe", "pycharm*.exe"], "verbatim": True}}
    assert appcontext.resolve_profile("pycharm64.exe", profiles)["verbatim"] is True
    assert appcontext.resolve_profile("pycharm.exe", profiles)["verbatim"] is True
    assert appcontext.resolve_profile("charm.exe", profiles) == {}
