"""Close the crash-recovery loop.

v1.2.0 added faulthandler writing native crash stacks to crash.log — but
nobody reads it. This module makes crashes actionable:

  * detect that the previous run crashed (crash.log grew since our last
    recorded baseline)
  * tell the user via a tray notification instead of failing silently
  * after 2 consecutive crashes while running on CUDA, automatically fall
    back to CPU for the next run — a machine with a flaky GPU driver gets a
    working (slower) dictation tool instead of a crash loop

All decision logic is pure and unit-tested; only read/write touch disk.
State lives in appdata/runtime_state.json.
"""
from __future__ import annotations

import json
import logging
import os

log = logging.getLogger("dictate.crashguard")

STATE_FILE = "runtime_state.json"


def state_path(appdata_dir: str) -> str:
    return os.path.join(appdata_dir, STATE_FILE)


def read_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_state(path: str, state: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError as ex:
        log.debug("could not write runtime state: %s", ex)


# ---- pure decision logic ----------------------------------------------------

def assess(crash_log_size: int, state: dict) -> tuple[bool, int]:
    """(crashed_last_run, consecutive_crashes) from the current crash.log size
    and the previous state. A shrunken file (user deleted/truncated it) is
    treated as no crash and re-baselines."""
    baseline = state.get("crash_log_size")
    if baseline is None:
        crashed = False  # first ever run — nothing to compare against
    else:
        crashed = crash_log_size > baseline
    consecutive = (state.get("consecutive_crashes", 0) + 1) if crashed else 0
    return crashed, consecutive


def should_force_cpu(consecutive_crashes: int, last_device: str | None) -> bool:
    """Two crashes in a row on CUDA = flaky GPU/driver; run on CPU instead.
    Never force anything on machines already on CPU (nothing to fall back to)."""
    return consecutive_crashes >= 2 and last_device == "cuda"


# ---- orchestration (called from main) --------------------------------------

def startup_check(appdata_dir: str, crash_log_path: str) -> dict:
    """Run at startup, BEFORE the engine is configured.

    Returns {"crashed": bool, "force_cpu": bool, "note": str|None} and
    persists the new baseline so the next run compares against today.
    """
    p = state_path(appdata_dir)
    state = read_state(p)
    try:
        size = os.path.getsize(crash_log_path)
    except OSError:
        size = 0
    crashed, consecutive = assess(size, state)
    force_cpu = should_force_cpu(consecutive, state.get("last_device"))
    note = None
    if force_cpu:
        note = ("Dictate crashed twice in a row on your GPU — running on CPU "
                "this time (slower but stable). Details: crash.log")
        log.warning("2+ consecutive CUDA crashes — forcing CPU for this run")
    elif crashed:
        note = ("Dictate crashed last time it ran. If it happens again it "
                "will switch to CPU mode. Details: crash.log")
        log.warning("previous run crashed (crash.log grew to %d bytes)", size)
    write_state(p, {"crash_log_size": size,
                    "consecutive_crashes": consecutive,
                    "last_device": state.get("last_device")})
    return {"crashed": crashed, "force_cpu": force_cpu, "note": note}


def record_device(appdata_dir: str, device: str | None):
    """Called once the model is loaded so the NEXT run knows what we ran on."""
    p = state_path(appdata_dir)
    state = read_state(p)
    state["last_device"] = device
    write_state(p, state)
