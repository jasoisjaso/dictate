"""Ticket 09: the overlay and guide must name fonts that exist here.

The bug is silent. Qt does not fail on a missing family — it substitutes one
at different metrics, so `Consolas` (monospace) becomes the proportional
system font on macOS and the guide's key-caps stop lining up, while the
overlay's fixed pixel widths are measured against a face nobody chose.

`pick_family` is the whole decision and it is pure: the candidate list and
the set of installed families are both arguments, so the macOS answer is
testable from Windows and the Windows answer from here.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import fonts


# What each platform actually has. Taken from a real machine, not invented:
# the macOS list is the subset of the 181 families Qt reported on macOS 26.6
# that we care about; the Windows list is the stock Windows 11 set.
MAC_INSTALLED = {".AppleSystemUIFont", "Helvetica Neue", "Helvetica", "Menlo",
                 "Monaco", "Courier New", "Arial"}
WIN_INSTALLED = {"Segoe UI", "Segoe UI Variable Text", "Consolas", "Tahoma",
                 "Courier New", "Arial"}


# ---- the pure choice --------------------------------------------------------

def test_first_installed_candidate_wins():
    assert fonts.pick_family(["Nope", "Menlo", "Monaco"], MAC_INSTALLED) == "Menlo"


def test_falls_back_to_last_candidate_when_none_installed():
    """Never return an empty family: Qt's own substitute beats no font at all."""
    assert fonts.pick_family(["Nope", "Alsonope"], set()) == "Alsonope"


def test_matching_is_case_insensitive():
    assert fonts.pick_family(["segoe ui"], WIN_INSTALLED) == "segoe ui"


# ---- Windows is unchanged ---------------------------------------------------

def test_windows_ui_family_is_still_segoe_ui():
    assert fonts.ui_family("Windows", WIN_INSTALLED) == "Segoe UI"


def test_windows_mono_family_is_still_consolas():
    assert fonts.mono_family("Windows", WIN_INSTALLED) == "Consolas"


# ---- macOS gets fonts that are actually there -------------------------------

def test_mac_ui_family_is_installed():
    assert fonts.ui_family("Darwin", MAC_INSTALLED) in MAC_INSTALLED


def test_mac_mono_family_is_installed():
    assert fonts.mono_family("Darwin", MAC_INSTALLED) in MAC_INSTALLED


def test_mac_mono_family_is_actually_monospace():
    """The guide's key-caps are drawn in the mono family. A proportional
    substitute is the exact bug this ticket exists for."""
    assert fonts.mono_family("Darwin", MAC_INSTALLED) in {"Menlo", "Monaco",
                                                          "SF Mono",
                                                          "Courier New"}


def test_mac_never_asks_for_a_windows_font():
    assert fonts.ui_family("Darwin", MAC_INSTALLED) not in {"Segoe UI", "Tahoma"}
    assert fonts.mono_family("Darwin", MAC_INSTALLED) != "Consolas"


# ---- an unknown platform still gets something usable ------------------------

def test_linux_or_unknown_platform_still_resolves():
    assert fonts.ui_family("Linux", {"Arial"})
    assert fonts.mono_family("Linux", {"Courier New"})
