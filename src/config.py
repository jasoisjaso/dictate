"""Config = packaged defaults deep-merged with the user's appdata TOML.
Writes only go to the appdata copy (install dir stays read-only)."""
from __future__ import annotations

import logging
import os
import platform
import re
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python 3.10 backport (pip install tomli)

try:
    from . import paths
except ImportError:
    import paths


def _default_toml_path() -> str:
    # One question, three answers, all of them in paths.resource_root():
    # a dev run reads the repo, Nuitka reads beside the exe, and a
    # PyInstaller .app reads Contents/Frameworks. Getting it wrong is silent
    # — a missing file parses as {} and the app starts with no defaults.
    return os.path.join(paths.resource_root(), "config", "settings.toml")


def _read(path: str) -> dict:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except (tomllib.TOMLDecodeError, OSError, ValueError) as ex:
        # A corrupt user settings file must NEVER stop the app from starting.
        # (Older builds could write an unquoted multi-word key like
        # `Purchase Order = "PO"`, which is invalid TOML.) Try to salvage the
        # valid lines, back up the broken file, and carry on with what we got.
        log = logging.getLogger("dictate.config")
        log.warning("settings file %s is invalid (%s); attempting recovery", path, ex)
        recovered = _salvage(path)
        try:
            import time as _t
            os.replace(path, path + f".corrupt-{int(_t.time())}.bak")
        except OSError:
            pass
        if recovered:
            log.warning("recovered %d settings section(s) from the broken file",
                        len(recovered))
        return recovered


def _salvage(path: str) -> dict:
    """Best-effort: re-parse a broken TOML file one section at a time, keeping
    only the lines/sections that parse. Anything unparseable is skipped so a
    single bad key can't wipe every setting."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except OSError:
        return {}
    out: dict = {}
    section = None
    buf: list[str] = []

    def _flush(sec, lines):
        if sec is None:
            return
        try:
            parsed = tomllib.loads("[" + sec + "]\n" + "\n".join(lines))
            # merge (handles dotted section names too)
            for k, v in parsed.items():
                out[k] = v
        except Exception:
            # drop bad lines individually, keep the good ones in this section
            good = {}
            for ln in lines:
                try:
                    good.update(tomllib.loads(ln))
                except Exception:
                    continue
            if good or sec not in out:
                out.setdefault(sec, {})
                if isinstance(out.get(sec), dict):
                    out[sec].update(good)

    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            _flush(section, buf)
            section, buf = s[1:-1], []
        else:
            buf.append(line)
    _flush(section, buf)
    return out


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def apply_platform_defaults(base: dict, system: str | None = None) -> dict:
    """Overlay this platform's hotkey defaults onto the packaged config.

    config/settings.toml ships key names chosen for a Windows PC keyboard as
    *values*, not absences, so `hk.get(name, <platform default>)` could never
    fall back — a Mac would be told to hold Right Ctrl, a key its keyboard
    doesn't have (docs/adr/0003). The ordering that fixes it:

        packaged defaults -> platform overlay -> the user's settings.toml

    Only [hotkeys] is touched, and only the key bindings; `mode` and every
    other section pass through. The user's own file is merged AFTER this, so
    a binding they chose still wins on every platform.
    """
    try:
        from . import hotkeys as _hotkeys
    except ImportError:
        import hotkeys as _hotkeys

    if system is None:
        system = platform.system()
    out = _deep_merge(base, {})           # copy; never mutate the caller's dict
    hk = dict(out.get("hotkeys", {}))
    hk.update(_hotkeys.defaults_for(system))
    out["hotkeys"] = hk
    return out


# Keys an Apple laptop's built-in keyboard does not have. F13-F20 exist only on
# Apple's full-size/extended keyboards; the rest are PC-only. A Windows setup
# carried over to a MacBook (settings.toml was copied, or the key was picked on
# a PC) leaves push-to-talk bound to one of these, and the hotkey is then
# simply unreachable — the app looks dead with no error anywhere.
_NOT_ON_BUILT_IN_MAC_KEYBOARD = frozenset(
    [f"f{i}" for i in range(13, 21)]
    + ["pause", "insert", "scroll_lock", "menu", "ctrl_r", "rctrl"]
)


def _external_keyboard_present() -> bool | None:
    """True if any non-built-in keyboard is attached, False if only the built-in
    one is, None when we cannot tell (non-mac, ioreg missing or unparseable).

    None must never trigger the fallback: overriding a binding on a guess would
    break a user whose extended keyboard we simply failed to see.
    """
    try:
        import plistlib
        import subprocess

        raw = subprocess.run(
            ["ioreg", "-r", "-c", "IOHIDDevice", "-d", "1", "-a"],
            capture_output=True, timeout=3, check=True,
        ).stdout
        devices = plistlib.loads(raw) if raw else []
    except Exception:
        return None
    keyboards = [d for d in devices if isinstance(d, dict)
                 and d.get("PrimaryUsagePage") == 1 and d.get("PrimaryUsage") == 6]
    if not keyboards:
        return None
    return any(not d.get("Built-In", False) for d in keyboards)


def fix_unreachable_ptt_key(cfg: dict, system: str | None = None,
                            _external=None) -> dict:
    """On a Mac with only the built-in keyboard, a push-to-talk key that keyboard
    does not have (F13, Pause, Right Ctrl...) falls back to the Mac default.

    The user's binding still wins whenever it could physically be pressed: an
    external keyboard is attached, or we cannot tell. Returns a new dict;
    never mutates the caller's.
    """
    if system is None:
        system = platform.system()
    if str(system).strip().lower() != "darwin":
        return cfg
    hk = cfg.get("hotkeys") or {}
    key = str(hk.get("push_to_talk_key", "")).strip().lower().strip("<>")
    if key not in _NOT_ON_BUILT_IN_MAC_KEYBOARD:
        return cfg
    external = (_external or _external_keyboard_present)()
    if external is not False:
        return cfg
    try:
        from . import hotkeys as _hotkeys
    except ImportError:
        import hotkeys as _hotkeys
    fallback = _hotkeys.defaults_for("Darwin")["push_to_talk_key"]
    logging.getLogger("dictate.config").warning(
        "push-to-talk key %r is not on this Mac's keyboard and no external "
        "keyboard is attached; using %r instead", key, fallback)
    out = _deep_merge(cfg, {})
    out["hotkeys"] = dict(hk, push_to_talk_key=fallback)
    return out


def load(defaults: dict | None = None) -> dict:
    base = defaults if defaults is not None else _read(_default_toml_path())
    base = apply_platform_defaults(base)
    user = _read(paths.config_path())
    return fix_unreachable_ptt_key(_deep_merge(base, user))


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


def export_config(path: str):
    """Export the current user settings to a JSON file."""
    import json
    cfg = _read(paths.config_path())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def import_config(path: str):
    """Import settings from a JSON file, replacing current user settings."""
    import json
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    save(cfg, merge=False)
