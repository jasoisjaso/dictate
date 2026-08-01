"""Result delivery: injecting the transcript into the focused app, macro
expansion, and the voice-edit commands that operate on the last injection.

Owns the last-injection bookkeeping (text, length, raw transcript) that the
voice commands and re-record need. Injection strategy (type vs paste) stays
in win32_input; this module decides per-result and never loses a dictation:
failed injection parks the text on the clipboard.
"""

import logging
import re

from PySide6.QtWidgets import QApplication

from . import voice_commands, win32_input
from .app_states import IDLE

log = logging.getLogger("dictate.delivery")


class TextDelivery:
    def __init__(self, app):
        self.app = app  # DictationTrayApp coordinator
        self.last_injected_len = 0
        self.last_injected_text = ""
        self.last_raw_text = ""      # raw transcript (pre-cleanup) for "redo verbatim"

    # ---- normal dictation result path ------------------------------------

    def on_result(self, text: str):
        app = self.app
        app.overlay.hide_overlay()
        app._set_state(IDLE)
        if not text:
            # empty transcript = we heard nothing usable; don't fail silently
            app.overlay.flash_toast(app.tr("didnt_catch"))
            return

        # If the result is ONLY whitespace/newlines (e.g. user said "novi red"
        # or "new line" on its own), inject it directly as keystrokes rather
        # than going through the paste path. A clipboard paste of just "\n"
        # can act as Enter in some apps (submit, send, execute). Typing it
        # via SendInput is safer and more predictable.
        if text.strip() == "" and text:
            # Pure whitespace/newline — type it directly
            win32_input.inject_text_native_unicode(text)
            self.last_injected_len = len(text)
            self.last_injected_text = text
            return

        # --- voice-edit commands (operate on the last dictation) -----------
        cmd = voice_commands.parse(text)
        if cmd is not None:
            self.run_voice_command(cmd)
            return

        # --- macro expansion (speak a phrase -> type a block) --------------
        macros = app.cfg.get("macros", {})
        if macros and text.lower().strip() in {k.lower() for k in macros}:
            for k, v in macros.items():
                if k.lower() == text.lower().strip():
                    text = v
                    break

        # --- normal dictation ---------------------------------------------
        app.history.add(text, app=app._rec_app)
        payload = text if text.endswith("\n") else text + " "
        # Terminals accept typed Unicode fine but eat synthesized Ctrl+V
        # more often than any other app class — type there, even long text.
        in_terminal = bool(app._rec_profile and app._rec_profile.get("verbatim"))
        # Some apps (modern Windows 11 Notepad) drop fast typed keystrokes;
        # their profile sets force_paste so we deliver via clipboard instead.
        force_paste = bool(app._rec_profile and app._rec_profile.get("force_paste"))
        if force_paste:
            how = "paste"
        else:
            how = win32_input.choose_injection(payload, mode=app.inject_mode,
                                               paste_threshold=app.paste_threshold,
                                               prefer_type=in_terminal)
        delivered = True
        try:
            if how == "paste":
                delivered = win32_input.inject_text_via_paste(payload)
            else:
                injected = win32_input.inject_text_native_unicode(payload)
                delivered = not win32_input.injection_suspect(injected, len(payload))
        except Exception:
            log.exception("text injection raised — falling back to clipboard")
            delivered = False
        if not delivered:
            # Never lose a dictation: if the target window swallowed the
            # input (elevated app, secure desktop, exclusive fullscreen),
            # park the text on the clipboard and tell the user.
            QApplication.clipboard().setText(text)
            app.overlay.flash_toast(app.tr("inject_failed"), ms=4000)
        self.last_injected_len = len(payload)
        self.last_injected_text = payload
        n_words = len(re.findall(r"[\w']+", text))
        app._session_words += n_words
        app._update_stats_label()
        # Context-aware undo hint: Ctrl+Z in a terminal sends EOF/SIGTSTP
        # (suspends the process), so show a different hint there.
        is_terminal = bool(app._rec_profile and app._rec_profile.get("verbatim"))
        undo_hint = app.tr("undo_hint_term" if is_terminal else "undo_hint")
        if delivered:
            if n_words == 1:
                app.overlay.flash_toast(app.tr("word_undo", undo=undo_hint))
            else:
                app.overlay.flash_toast(
                    app.tr("words_undo", n=n_words, undo=undo_hint))
        # Continuous mode: auto-restart recording after a brief pause
        if app.mode == "continuous" and not getattr(app, "_continuous_stop", False):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(800, app._begin_recording)

    # ---- voice-edit commands --------------------------------------------

    def run_voice_command(self, cmd):
        """Execute a parsed voice-edit command against the last injection."""
        app = self.app
        if cmd.kind == "scratch":
            win32_input.inject_backspaces(self.last_injected_len)
            self.last_injected_len = 0
            self.last_injected_text = ""
            app.overlay.flash_toast(app.tr("scratched"))
            return
        if cmd.kind == "delete_words":
            back = voice_commands.tail_word_len(self.last_injected_text, cmd.n)
            # never backspace more than we actually injected, so a stale buffer
            # can't eat text the user typed themselves between dictations
            back = min(back, self.last_injected_len)
            if back:
                win32_input.inject_backspaces(back)
                self.last_injected_text = self.last_injected_text[:-back]
                self.last_injected_len = len(self.last_injected_text)
            app.overlay.flash_toast(
                f"deleted {cmd.n} word{'s' if cmd.n != 1 else ''}")
            return
        if cmd.kind == "recase":
            old = self.last_injected_text
            if not old.strip():
                app.overlay.flash_toast(app.tr("nothing_to_change"))
                return
            trailing = old[len(old.rstrip()):]
            new = voice_commands.apply_recase(old.rstrip(), cmd.mode) + trailing
            win32_input.inject_backspaces(len(old))
            how = win32_input.choose_injection(new, mode=app.inject_mode,
                                               paste_threshold=app.paste_threshold)
            if how == "paste":
                win32_input.inject_text_via_paste(new)
            else:
                win32_input.inject_text_native_unicode(new)
            self.last_injected_text = new
            self.last_injected_len = len(new)
            app.overlay.flash_toast({"upper": "ALL CAPS",
                                     "lower": "lowercase",
                                     "title": "Capitalized"}.get(cmd.mode, "done"))
            return
        if cmd.kind == "redo_verbatim":
            raw = self.last_raw_text
            if not raw.strip():
                app.overlay.flash_toast(app.tr("nothing_to_redo"))
                return
            # Backspace the last injection, re-inject the raw words as-is
            if self.last_injected_len > 0:
                win32_input.inject_backspaces(self.last_injected_len)
            payload = raw if raw.endswith("\n") else raw + " "
            how = win32_input.choose_injection(payload, mode=app.inject_mode,
                                               paste_threshold=app.paste_threshold)
            if how == "paste":
                win32_input.inject_text_via_paste(payload)
            else:
                win32_input.inject_text_native_unicode(payload)
            self.last_injected_text = payload
            self.last_injected_len = len(payload)
            app.overlay.flash_toast(app.tr("redone"))
            return
        if cmd.kind == "delete_sentence":
            # Delete from the last sentence boundary (. ! ? \n) to the end
            text = self.last_injected_text
            if not text.strip():
                app.overlay.flash_toast("nothing to delete")
                return
            # Find the last sentence boundary before the final character
            rstrip = text.rstrip()
            search = rstrip[:-1] if len(rstrip) > 1 else rstrip
            boundary = -1
            for ch in ".!?\n":
                pos = search.rfind(ch)
                if pos > boundary:
                    boundary = pos
            if boundary >= 0:
                # Delete everything after the boundary
                to_delete = len(text) - (boundary + 1)
                to_delete = min(to_delete, self.last_injected_len)
            else:
                # No sentence boundary — delete the whole thing
                to_delete = self.last_injected_len
            if to_delete > 0:
                win32_input.inject_backspaces(to_delete)
                self.last_injected_text = text[:len(text) - to_delete]
                self.last_injected_len = len(self.last_injected_text)
            app.overlay.flash_toast(app.tr("deleted_sentence"))
            return
        if cmd.kind == "format":
            if cmd.mode == "select_all":
                # Ctrl+A — select all text in the current field
                win32_input._send_inputs([
                    win32_input._vk_event(win32_input.VK_CONTROL),
                    win32_input._vk_event(0x41),  # 'A'
                    win32_input._vk_event(0x41, win32_input.KEYEVENTF_KEYUP),
                    win32_input._vk_event(win32_input.VK_CONTROL, win32_input.KEYEVENTF_KEYUP),
                ])
                app.overlay.flash_toast(app.tr("selected_all"))
                return
            old = self.last_injected_text
            if not old.strip():
                app.overlay.flash_toast("nothing to format")
                return
            trailing = old[len(old.rstrip()):]
            stripped = old.rstrip()
            if cmd.mode == "bold":
                new = f"**{stripped}**" + trailing
            elif cmd.mode == "italic":
                new = f"*{stripped}*" + trailing
            else:
                return
            win32_input.inject_backspaces(len(old))
            how = win32_input.choose_injection(new, mode=app.inject_mode,
                                               paste_threshold=app.paste_threshold)
            if how == "paste":
                win32_input.inject_text_via_paste(new)
            else:
                win32_input.inject_text_native_unicode(new)
            self.last_injected_text = new
            self.last_injected_len = len(new)
            app.overlay.flash_toast(cmd.mode)
            return
        if cmd.kind == "replace":
            old = self.last_injected_text
            if not old.strip():
                app.overlay.flash_toast("nothing to replace")
                return
            old_text = old.rstrip()
            trailing = old[len(old_text):]
            new_text = old_text.replace(cmd.old, cmd.new)
            if new_text == old_text:
                app.overlay.flash_toast(f"didn't find '{cmd.old}'")
                return
            new_payload = new_text + trailing
            win32_input.inject_backspaces(len(old))
            how = win32_input.choose_injection(new_payload, mode=app.inject_mode,
                                               paste_threshold=app.paste_threshold)
            if how == "paste":
                win32_input.inject_text_via_paste(new_payload)
            else:
                win32_input.inject_text_native_unicode(new_payload)
            self.last_injected_text = new_payload
            self.last_injected_len = len(new_payload)
            app.overlay.flash_toast(f"replaced '{cmd.old}' with '{cmd.new}'")
            return
