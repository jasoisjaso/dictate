"""Config = packaged defaults deep-merged with the user's appdata TOML.
Writes only go to the appdata copy (install dir stays read-only)."""
from __future__ import annotations

import os
import re
import sys
import tomllib

try:
    from . import paths
except ImportError:
    import paths


def _default_toml_path() -> str:
    # Frozen (Nuitka): config/ sits next to the executable.
    # Dev: config/settings.toml relative to repo root (src/../config).
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.join(os.path.dirname(__file__), "..")
    return os.path.join(base, "config", "settings.toml")


def _read(path: str) -> dict:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load(defaults: dict | None = None) -> dict:
    base = defaults if defaults is not None else _read(_default_toml_path())
    user = _read(paths.config_path())
    return _deep_merge(base, user)


def save(user_cfg: dict, *, merge: bool = True) -> None:
    """Persist the user overlay. Minimal TOML writer (str/int/float/bool and
    flat lists of those), two levels deep — matches our schema, no dependency
    on tomli-w.

    merge=True (default) deep-merges onto whatever is already in the user's
    settings.toml, so saving from a GUI that only knows about *some* keys can
    never silently wipe keys the user hand-edited (ollama_*, app_profiles,
    vad, injection, ...). Pass merge=False to write exactly what's given."""
    if merge:
        existing = _read(paths.config_path())
        user_cfg = _deep_merge(existing, user_cfg)
    lines = []
    for section, body in user_cfg.items():
        if isinstance(body, dict):
            lines.append(f"[{_key(section)}]")
            # scalars/lists first, then nested tables — a [a.b] header must not
            # appear before the remaining bare keys of [a] or they'd bind to it
            nested = []
            for k, v in body.items():
                if isinstance(v, dict):
                    nested.append((k, v))
                else:
                    lines.append(f"{_key(k)} = {_fmt(v)}")
            for k, v in nested:
                lines.append(f"[{_key(section)}.{_key(k)}]")
                for kk, vv in v.items():
                    lines.append(f"{_key(kk)} = {_fmt(vv)}")
            lines.append("")
        else:
            lines.append(f"{_key(section)} = {_fmt(body)}")
    with open(paths.config_path(), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def _key(k) -> str:
    """A TOML key. Bare (letters/digits/_/-) stays bare; anything else — e.g.
    a multi-word dictionary entry like "hello acrylic" — gets quoted so the
    written file is valid TOML and reloads cleanly."""
    k = str(k)
    if _BARE_KEY.match(k):
        return k
    return '"' + k.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'
