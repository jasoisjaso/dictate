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


def app_data_dir() -> str:
    if is_portable():
        d = os.path.join(install_root(), "Data")
    elif platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        d = os.path.join(base, APP_NAME)
    else:  # WSL/dev
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        d = os.path.join(base, APP_NAME)
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
