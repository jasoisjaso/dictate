"""Update check against GitHub releases — the missing update path.

Without this, someone who installs v1.2.0 today would NEVER learn that a fix
exists. On startup (after the model is ready, off the GUI thread) we ask the
GitHub API for the latest release tag and, if it's newer than the running
version, the tray shows a clickable "update available" notification.

Design constraints:
  * fail-silent: no network, rate-limited, API change — all mean "no update
    info", never an error the user sees
  * throttled: at most one real HTTP request per `min_interval_h` hours,
    tracked in appdata/update_state.json — a dictation tool must not ping
    GitHub on every launch
  * privacy: the request carries no identifying payload beyond a UA string
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
from dataclasses import dataclass

log = logging.getLogger("dictate.update")

STATE_FILE = "update_state.json"


@dataclass
class Update:
    tag: str
    url: str


def parse_version(tag: str) -> tuple[int, ...] | None:
    """'v1.2.1' / '1.2.1' -> (1, 2, 1); None if unparseable."""
    if not tag:
        return None
    m = re.match(r"v?(\d+(?:\.\d+)*)", tag.strip())
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split("."))


def is_newer(latest_tag: str, current_version: str) -> bool:
    latest = parse_version(latest_tag)
    current = parse_version(current_version)
    if latest is None or current is None:
        return False
    # pad to equal length so 1.3 vs 1.2.1 compares sanely
    n = max(len(latest), len(current))
    return (latest + (0,) * (n - len(latest))) > (current + (0,) * (n - len(current)))


def _throttled(state_path: str, min_interval_h: float) -> bool:
    try:
        with open(state_path, encoding="utf-8") as f:
            last = json.load(f).get("last_check", 0)
        return (time.time() - last) < min_interval_h * 3600
    except Exception:
        return False


def _mark_checked(state_path: str):
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"last_check": time.time()}, f)
    except OSError:
        pass


def check_github(repo: str, current_version: str, state_dir: str | None = None,
                 min_interval_h: float = 20.0, timeout: float = 6.0
                 ) -> Update | None:
    """Return an Update if `repo` has a release newer than current_version.
    Throttled via a state file in state_dir; fail-silent on any error."""
    state_path = None
    if state_dir:
        state_path = os.path.join(state_dir, STATE_FILE)
        if _throttled(state_path, min_interval_h):
            return None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers={"User-Agent": "Dictate-update-check",
                     "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        if state_path:
            _mark_checked(state_path)
        tag = data.get("tag_name", "")
        url = data.get("html_url", f"https://github.com/{repo}/releases")
        if is_newer(tag, current_version):
            log.info("update available: %s (running %s)", tag, current_version)
            return Update(tag=tag, url=url)
        return None
    except Exception as ex:
        log.debug("update check skipped (%s)", ex)
        return None
