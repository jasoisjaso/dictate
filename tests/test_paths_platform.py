"""Where user data lives, per platform.

Settings, logs and several hundred megabytes of Models have to land where the
running operating system's users — and their uninstallers, backup tools and
Migration Assistant — expect to find them. macOS was falling through to the
Linux XDG branch, which is a directory no Mac user or uninstaller looks in.

The seam is pure: `resolve_app_data_dir` takes the platform, the environment
and the home directory as arguments and creates nothing, so every platform's
answer is testable from every platform. `app_data_dir()` is the thin wrapper
that asks the real machine and makes the directory.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import paths  # noqa: E402


APP = paths.APP_NAME


def resolve(system, env=None, home="/home/u", install_root="/opt/app",
            portable=False):
    return paths.resolve_app_data_dir(system=system, env=env or {}, home=home,
                                      install_root=install_root,
                                      portable=portable)


# ---- macOS -----------------------------------------------------------------


def test_macos_lands_in_application_support():
    d = resolve("Darwin", home="/Users/jaso")
    assert d == os.path.join("/Users/jaso", "Library", "Application Support", APP)


def test_macos_ignores_xdg_data_home():
    """XDG_DATA_HOME is a Linux convention. A Mac that happens to have it set
    (a stray shell profile) must still use Application Support, or the Models
    hide somewhere no uninstaller looks."""
    d = resolve("Darwin", env={"XDG_DATA_HOME": "/tmp/xdg"}, home="/Users/jaso")
    assert "/tmp/xdg" not in d
    assert "Application Support" in d


# ---- Windows, unchanged ----------------------------------------------------


def test_windows_uses_localappdata():
    d = resolve("Windows", env={"LOCALAPPDATA": r"C:\Users\Jaso\AppData\Local"})
    assert d == os.path.join(r"C:\Users\Jaso\AppData\Local", APP)


def test_windows_without_localappdata_falls_back_to_home():
    d = resolve("Windows", env={}, home=r"C:\Users\Jaso")
    assert d == os.path.join(r"C:\Users\Jaso", APP)


# ---- Linux / WSL, unchanged ------------------------------------------------


def test_linux_honours_xdg_data_home():
    d = resolve("Linux", env={"XDG_DATA_HOME": "/tmp/xdg"})
    assert d == os.path.join("/tmp/xdg", APP)


def test_linux_defaults_to_local_share():
    d = resolve("Linux", env={}, home="/home/u")
    assert d == os.path.join("/home/u", ".local", "share", APP)


# ---- portable beats every platform -----------------------------------------


def test_portable_keeps_everything_beside_the_app_on_any_platform():
    """A portable install writes nothing to the host, whichever OS it is
    plugged into."""
    for system in ("Darwin", "Windows", "Linux"):
        d = resolve(system, env={"LOCALAPPDATA": r"C:\x", "XDG_DATA_HOME": "/y"},
                    install_root="/Volumes/USB/Dictate", portable=True)
        assert d == os.path.join("/Volumes/USB/Dictate", "Data")


# ---- the real wrapper agrees with the pure answer ---------------------------


def test_the_live_directory_matches_the_resolver_for_this_machine():
    import platform

    expected = paths.resolve_app_data_dir(
        system=platform.system(), env=os.environ,
        home=os.path.expanduser("~"), install_root=paths.install_root(),
        portable=paths.is_portable())
    assert paths.app_data_dir() == expected


def test_the_live_directory_exists_after_asking_for_it():
    assert os.path.isdir(paths.app_data_dir())
