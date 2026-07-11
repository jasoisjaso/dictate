"""Filesystem locations shared by dev runs and the frozen exe."""
import os
import platform

APP_NAME = "TranscribeDictate"


def app_data_dir() -> str:
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
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
