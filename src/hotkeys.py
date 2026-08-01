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


def parse_key(name: str):
    """Config string -> pynput key object. Accepts single chars, <ctrl> style,
    and friendly names like ctrl_r / alt_gr / f9 / pause / space."""
    from pynput import keyboard

    n = name.strip().lower().strip("<>")
    special = {
        "ctrl_r": keyboard.Key.ctrl_r, "rctrl": keyboard.Key.ctrl_r,
        "ctrl_l": keyboard.Key.ctrl_l, "lctrl": keyboard.Key.ctrl_l,
        "ctrl": keyboard.Key.ctrl,
        "alt_r": keyboard.Key.alt_r, "alt_gr": keyboard.Key.alt_gr,
        "altgr": keyboard.Key.alt_gr, "alt_l": keyboard.Key.alt_l,
        "alt": keyboard.Key.alt,
        "shift_r": keyboard.Key.shift_r, "shift": keyboard.Key.shift,
        "cmd": keyboard.Key.cmd, "win": keyboard.Key.cmd,
        "pause": keyboard.Key.pause, "scroll_lock": keyboard.Key.scroll_lock,
        "caps_lock": keyboard.Key.caps_lock, "menu": keyboard.Key.menu,
        "space": keyboard.Key.space, "esc": keyboard.Key.esc,
        "tab": keyboard.Key.tab, "insert": keyboard.Key.insert,
    }
    for i in range(1, 13):
        special[f"f{i}"] = getattr(keyboard.Key, f"f{i}")
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
