"""Where the packaged files live, in a dev run and inside a bundle.

`config/settings.toml` ships *with* the app — it is the packaged default every
user setting is merged onto. Finding it has always been "the directory the
executable is in", which is true for the Nuitka build on Windows and false for
a PyInstaller `.app`: there the executable sits in `Contents/MacOS` while the
data files are unpacked to `Contents/Frameworks`, and the bootloader hands
that path over as `sys._MEIPASS`. Getting it wrong is not loud — `_read`
returns `{}` for a missing file — so the app would start with no packaged
defaults at all and only the platform hotkey overlay to go on.

The seam is pure: the freeze flag, the executable path and the bundle's
unpack directory are all arguments, so the bundle's answer is testable from a
dev run on any platform.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import paths  # noqa: E402


REPO = os.path.dirname(os.path.dirname(os.path.abspath(paths.__file__)))


# ---- a dev run reads the repo -----------------------------------------------


def test_dev_run_resolves_to_the_repo_root():
    d = paths.resolve_resource_root(frozen=False, executable="/usr/bin/python3",
                                    meipass=None, source_root=REPO)
    assert d == REPO


def test_dev_run_ignores_a_stray_meipass():
    """Nothing sets _MEIPASS outside a bundle, but if something did, an
    unfrozen run must still read the checked-out config rather than a stale
    unpack directory from another process."""
    d = paths.resolve_resource_root(frozen=False, executable="/usr/bin/python3",
                                    meipass="/tmp/_MEIxyz", source_root=REPO)
    assert d == REPO


# ---- a PyInstaller bundle reads its unpack directory ------------------------


def test_pyinstaller_bundle_uses_the_unpack_directory():
    d = paths.resolve_resource_root(
        frozen=True,
        executable="/Applications/Dictate.app/Contents/MacOS/Dictate",
        meipass="/Applications/Dictate.app/Contents/Frameworks",
        source_root=REPO)
    assert d == "/Applications/Dictate.app/Contents/Frameworks"


def test_a_frozen_build_without_meipass_falls_back_to_the_executable():
    """Nuitka sets no _MEIPASS and puts config/ beside the exe. That build
    must keep working exactly as it does today.

    The executable path is written in this platform's own separators —
    os.path.dirname is not portable across them, and the contract under test
    is "the directory the executable is in", not string surgery on a foreign
    path shape.
    """
    exe = os.path.join(os.sep + "opt", "Dictate", "Dictate.exe")
    d = paths.resolve_resource_root(frozen=True, executable=exe, meipass=None,
                                    source_root=REPO)
    assert d == os.path.dirname(exe)


# ---- the live answer, and the file it is there to find ----------------------


def test_the_live_resource_root_holds_the_packaged_config():
    assert os.path.isfile(os.path.join(paths.resource_root(),
                                       "config", "settings.toml"))


def test_config_reads_its_defaults_from_the_resource_root():
    import config

    assert config._default_toml_path() == os.path.join(
        paths.resource_root(), "config", "settings.toml")
    assert os.path.isfile(config._default_toml_path())


def test_packaged_defaults_are_actually_loaded():
    """The regression this file exists for: a wrong root is silent, because a
    missing settings.toml parses as an empty dict."""
    import config

    base = config._read(config._default_toml_path())
    assert base, "packaged defaults came back empty"
    assert "whisper" in base


# ---- user data is not the same question -------------------------------------


def test_user_data_is_never_inside_the_bundle():
    """Read-only resources and writable user data are two different roots; an
    `.app` is signed and must never be written into."""
    inside = paths.resolve_resource_root(
        frozen=True,
        executable="/Applications/Dictate.app/Contents/MacOS/Dictate",
        meipass="/Applications/Dictate.app/Contents/Frameworks",
        source_root=REPO)
    data = paths.resolve_app_data_dir(
        system="Darwin", env={}, home="/Users/jaso",
        install_root=inside, portable=False)
    assert ".app/" not in data
    assert data.startswith("/Users/jaso/Library/Application Support")
