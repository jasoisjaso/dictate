"""Per-user start-on-login via a Startup-folder shortcut. No admin needed."""
import logging
import os
import subprocess
import sys

log = logging.getLogger("dictate.startup")

_LNK_NAME = "Dictate.lnk"


def _startup_dir() -> str:
    return os.path.join(os.environ.get("APPDATA", ""),
                        "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup")


def _lnk_path() -> str:
    return os.path.join(_startup_dir(), _LNK_NAME)


def _launch_target() -> tuple[str, str]:
    """(target, args) the shortcut should run."""
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    # dev run: pythonw -m src.main from the repo root
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    return pyw, f'-m src.main'  # WorkingDirectory is set to the repo root


def is_enabled() -> bool:
    return os.path.exists(_lnk_path())


def enable() -> bool:
    target, args = _launch_target()
    workdir = (os.path.dirname(target) if getattr(sys, "frozen", False)
               else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{_lnk_path()}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.Arguments = '{args}'; "
        f"$s.WorkingDirectory = '{workdir}'; "
        "$s.Save()"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=15, check=True)
        return True
    except Exception as ex:
        log.warning("could not create startup shortcut: %s", ex)
        return False


def disable() -> bool:
    try:
        os.remove(_lnk_path())
        return True
    except FileNotFoundError:
        return True
    except Exception as ex:
        log.warning("could not remove startup shortcut: %s", ex)
        return False
