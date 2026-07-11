"""Config = packaged defaults deep-merged with the user's appdata TOML.
Writes only go to the appdata copy (install dir stays read-only)."""
from __future__ import annotations

import os
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


def save(user_cfg: dict) -> None:
    """Persist the user overlay. Minimal TOML writer (str/int/float/bool),
    two levels deep — matches our schema, no dependency on tomli-w."""
    lines = []
    for section, body in user_cfg.items():
        lines.append(f"[{section}]")
        for k, v in body.items():
            lines.append(f"{k} = {_fmt(v)}")
        lines.append("")
    with open(paths.config_path(), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'
