"""Filesystem locations shared by dev runs and the frozen exe.

Portable mode: if a file named `portable.txt` sits next to the executable
(or at the repo root in dev runs), ALL user data — config, models, logs —
lives in a `Data` folder beside it instead of %LOCALAPPDATA%. Drop the
folder on a USB stick and it carries its brain with it; nothing is written
to the host machine except a tiny lock file in %TEMP%.
"""
import os
import platform
import sys

APP_NAME = "TranscribeDictate"
PORTABLE_MARKER = "portable.txt"


def install_root() -> str:
    """Directory the app runs from (exe dir when frozen, repo root in dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_portable() -> bool:
    return os.path.exists(os.path.join(install_root(), PORTABLE_MARKER))


def resolve_resource_root(frozen: bool, executable: str, meipass: str | None,
                          source_root: str) -> str:
    """Where the packaged read-only files live, as a pure decision.

    Three shapes, and they disagree:

      * a dev run  — the repo root, two levels up from this file
      * Nuitka     — beside the executable (what Windows ships today)
      * PyInstaller — the bootloader's unpack directory, which for a `.app` is
        `Contents/Frameworks` while the executable sits in `Contents/MacOS`

    _MEIPASS is only trusted when the run is actually frozen: a stray variable
    inherited from another process must never redirect a dev run at a stale
    unpack directory.

    This is NOT where user data goes — see resolve_app_data_dir. An `.app` is
    signed and read-only; writing into it breaks the signature.
    """
    if frozen:
        return meipass or os.path.dirname(os.path.abspath(executable))
    return source_root


def resource_root() -> str:
    """The resolved read-only resource directory for this run."""
    return resolve_resource_root(
        frozen=bool(getattr(sys, "frozen", False)),
        executable=sys.executable,
        meipass=getattr(sys, "_MEIPASS", None),
        source_root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )


def resolve_app_data_dir(system: str, env, home: str, install_root: str,
                         portable: bool) -> str:
    """Where user data belongs, as a pure decision. Creates nothing.

    Everything the answer depends on is an argument, so every platform's
    directory is testable from every platform.

    Portable wins over all of it: a portable install writes nothing to the
    host machine, whichever OS it is plugged into.

    macOS gets ~/Library/Application Support/<app> rather than the Linux XDG
    branch it used to fall through to. It matters because of the size — a
    user, an uninstaller, or Migration Assistant has to be able to find
    several hundred megabytes of Models, and no Mac tool looks in
    ~/.local/share. XDG_DATA_HOME is deliberately ignored there: a stray
    shell profile that exports it must not hide the Models.
    """
    if portable:
        return os.path.join(install_root, "Data")
    if system == "Windows":
        return os.path.join(env.get("LOCALAPPDATA") or home, APP_NAME)
    if system == "Darwin":
        return os.path.join(home, "Library", "Application Support", APP_NAME)
    # Linux / WSL / dev
    base = env.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    return os.path.join(base, APP_NAME)


def app_data_dir() -> str:
    """The resolved directory for this machine, created if it is missing."""
    d = resolve_app_data_dir(
        system=platform.system(),
        env=os.environ,
        home=os.path.expanduser("~"),
        install_root=install_root(),
        portable=is_portable(),
    )
    os.makedirs(d, exist_ok=True)
    return d


def models_dir() -> str:
    d = os.path.join(app_data_dir(), "models")
    os.makedirs(d, exist_ok=True)
    return d


def config_path() -> str:
    return os.path.join(app_data_dir(), "settings.toml")


def log_path() -> str:
    return os.path.join(app_data_dir(), "dictate.log")
