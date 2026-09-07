"""Global hotkeys (push-to-talk or toggle) via pynput.

Trigger models (config [hotkeys].mode):
  push_to_talk (default) — hold a single key (default Right Ctrl), speak,
    release. Right Ctrl alone triggers nothing in terminals / PowerShell / WSL,
    which is why it replaced the old Ctrl+Alt+D combo.
  toggle — tap the key once to start (auto-stops after silence), tap to stop.
    This is the hands-free mode.

Callbacks fire on pynput's listener thread. The app wires Qt signal .emit
callables for anything that must cross into the GUI thread; the pause and
re-record callbacks are called directly (same wiring as before the split).
"""

import logging

log = logging.getLogger("dictate.hotkeys")


# Config name -> the attribute on pynput's Key enum it means. Several names
# are aliases for one key (rctrl/ctrl_r, win/cmd). Which of these actually
# EXIST is platform-specific: macOS has no pause, scroll_lock, menu, insert
# or alt_gr, so the table has to be built from what the enum really defines.
_KEY_ALIASES = {
    "ctrl_r": "ctrl_r", "rctrl": "ctrl_r",
    "ctrl_l": "ctrl_l", "lctrl": "ctrl_l",
    "ctrl": "ctrl",
    "alt_r": "alt_r", "alt_gr": "alt_gr", "altgr": "alt_gr",
    "alt_l": "alt_l", "alt": "alt",
    "shift_r": "shift_r", "shift": "shift",
    "cmd": "cmd", "win": "cmd", "cmd_r": "cmd_r", "rcmd": "cmd_r",
    "pause": "pause", "scroll_lock": "scroll_lock",
    "caps_lock": "caps_lock", "menu": "menu",
    "space": "space", "esc": "esc",
    "tab": "tab", "insert": "insert",
}
for _i in range(1, 21):
    _KEY_ALIASES[f"f{_i}"] = f"f{_i}"


def available_keys(key_enum) -> dict:
    """Config name -> key object, for the keys this platform actually has.

    Names the running enum doesn't define are simply absent from the table,
    so callers get the ordinary unknown-key fallback instead of an
    AttributeError at import time.
    """
    table = {}
    for name, attr in _KEY_ALIASES.items():
        key = getattr(key_enum, attr, None)
        if key is not None:
            table[name] = key
    return table


# Shipped defaults per platform (docs/adr/0003). An empty string means the
# action ships UNBOUND: the key either doesn't exist on that keyboard, or a
# bare press of it does something alarming (macOS ships fnState unset, so F6-F9
# are media/brightness). Settings can still bind them.
_DEFAULTS_WINDOWS = {
    "push_to_talk_key": "ctrl_r",
    "toggle_key": "f9",
    "abort_key": "esc",
    "copy_key": "f8",
    "mode_cycle_key": "f7",
    "pause_key": "pause",
    "rerecord_key": "f6",
}

# Right Option, not Right Ctrl (absent on Apple laptops) and not Right Command
# (a held Cmd turns every other keypress into a shortcut fired at the app you
# are dictating into). copy_key stays bound as fn+F8: it is the rescue path
# when text lands in the wrong window.
_DEFAULTS_MACOS = {
    "push_to_talk_key": "alt_r",
    "toggle_key": "",
    "abort_key": "esc",
    "copy_key": "f8",
    "mode_cycle_key": "",
    "pause_key": "",
    "rerecord_key": "",
}


def defaults_for(system: str) -> dict:
    """The shipped hotkey defaults for an OS name (platform.system())."""
    if str(system).strip().lower() == "darwin":
        return dict(_DEFAULTS_MACOS)
    return dict(_DEFAULTS_WINDOWS)


def parse_key(name: str):
    """Config string -> pynput key object. Accepts single chars, <ctrl> style,
    and friendly names like ctrl_r / alt_r / f9 / space. A name this platform
    has no key for falls back with a warning, same as an unknown name.

    An empty name means the action is deliberately unbound and returns None —
    falling back there would silently bind it to the push-to-talk key.
    """
    from pynput import keyboard

    n = (name or "").strip().lower().strip("<>")
    if not n:
        return None
    special = available_keys(keyboard.Key)
    if n in special:
        return special[n]
    if len(n) == 1:
        return keyboard.KeyCode.from_char(n)
    log.warning("unknown key %r; falling back to Right Ctrl", name)
    return keyboard.Key.ctrl_r


def pretty_key(name: str) -> str:
    return {
        "ctrl_r": "Right Ctrl", "ctrl_l": "Left Ctrl", "alt_r": "Right Alt",
        "alt_gr": "Right Alt", "pause": "Pause", "menu": "Menu key",
        "caps_lock": "Caps Lock", "scroll_lock": "Scroll Lock",
    }.get(name.strip().lower(), name.strip().upper() if len(name.strip()) == 1
          else name.strip().title())


class HotkeyController:
    """Owns the global pynput listener and the key-to-action routing.

    `callbacks` keys: ptt_start, ptt_stop, abort, toggle, copy, mode_cycle,
    pause, rerecord. All optional-safe: missing keys simply never fire.
    """

    def __init__(self, mode: str, key_names: dict, callbacks: dict):
        self.mode = mode
        self.names = dict(key_names)
        self.cb = dict(callbacks)
        self._ptt_down = False
        self._listener = None

    def start(self):
        from pynput import keyboard

        self._ptt_key = parse_key(self.names["ptt"])
        self._toggle_key = parse_key(self.names["toggle"])
        self._abort_key = parse_key(self.names["abort"])
        self._copy_key = parse_key(self.names["copy"])
        self._mode_cycle_key = parse_key(self.names["mode_cycle"])
        self._pause_key = parse_key(self.names["pause"])
        self._rerecord_key = parse_key(self.names["rerecord"])
        self._ptt_down = False
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()
        log.info("hotkeys: mode=%s ptt=%s toggle=%s abort=%s copy=%s mode_cycle=%s pause=%s",
                 self.mode, self.names["ptt"], self.names["toggle"],
                 self.names["abort"], self.names["copy"],
                 self.names["mode_cycle"], self.names["pause"])

    def stop(self):
        try:
            self._listener.stop()
        except Exception:
            pass
        self._listener = None

    def reset_ptt(self):
        """Forget a held push-to-talk key (used by abort so a stuck 'down'
        flag can't swallow the next press)."""
        self._ptt_down = False

    @staticmethod
    def _key_matches(key, target) -> bool:
        if target is None:
            return False
        if key == target:
            return True
        kc = getattr(key, "char", None)
        tc = getattr(target, "char", None)
        if kc and tc:
            return kc.lower() == tc.lower()
        return False

    def _on_press(self, key):
        try:
            if self.mode == "push_to_talk" and self._key_matches(key, self._ptt_key):
                if not self._ptt_down:          # ignore auto-repeat
                    self._ptt_down = True
                    self.cb["ptt_start"]()
                return
            if self._key_matches(key, self._abort_key):
                self.cb["abort"]()
                return
            if self.mode == "toggle" and self._key_matches(key, self._toggle_key):
                self.cb["toggle"]()
                return
            if self._key_matches(key, self._copy_key):
                self.cb["copy"]()
                return
            if self._key_matches(key, self._mode_cycle_key):
                self.cb["mode_cycle"]()
                return
            if self._key_matches(key, self._pause_key):
                self.cb["pause"]()
                return
            if self._key_matches(key, self._rerecord_key):
                self.cb["rerecord"]()
                return
        except Exception:
            log.exception("hotkey on_press error")

    def _on_release(self, key):
        try:
            if self.mode == "push_to_talk" and self._key_matches(key, self._ptt_key):
                if self._ptt_down:
                    self._ptt_down = False
                    self.cb["ptt_stop"]()
        except Exception:
            log.exception("hotkey on_release error")
