"""The delivery path, exercised through a fake Input Backend.

Delivery used to call the Windows module directly in ~30 places, so none of
it could be tested anywhere but Windows. With one Injection interface in
front of the backends, a fake that records (operation, payload) tuples makes
the whole path verifiable on any platform: type vs paste selection,
multi-line always pasting, the whitespace-only special case, the
failed-injection clipboard rescue, and the voice-edit commands.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

pytest.importorskip("PySide6", reason="delivery imports Qt for the clipboard rescue")

from src import delivery, input_backend, voice_commands  # noqa: E402


class FakeBackend:
    """Records what Injection was asked to do, and can refuse to deliver."""

    def __init__(self, paste_ok=True, type_ok=True):
        self.ops = []
        self.paste_ok = paste_ok
        self.type_ok = type_ok

    def inject_text(self, text):
        self.ops.append(("type", text))
        return len(text) if self.type_ok else 0

    def paste_text(self, text):
        self.ops.append(("paste", text))
        return self.paste_ok

    def backspaces(self, count):
        self.ops.append(("backspace", count))
        return count

    def select_all(self):
        self.ops.append(("select_all", None))
        return True

    @property
    def kinds(self):
        return [op for op, _ in self.ops]


class FakeOverlay:
    def __init__(self):
        self.toasts = []

    def hide_overlay(self):
        pass

    def flash_toast(self, text, ms=None):
        self.toasts.append(text)


class FakeHistory:
    def __init__(self):
        self.entries = []

    def add(self, text, app=None):
        self.entries.append(text)


class FakeApp:
    """The coordinator surface TextDelivery actually touches."""

    def __init__(self, profile=None, inject_mode="auto", paste_threshold=300):
        self.overlay = FakeOverlay()
        self.history = FakeHistory()
        self.cfg = {}
        self.inject_mode = inject_mode
        self.paste_threshold = paste_threshold
        self.mode = "normal"
        self._rec_app = None
        self._rec_profile = profile
        self._session_words = 0
        self.state = None

    def tr(self, key, **kw):
        return key

    def _set_state(self, state):
        self.state = state

    def _update_stats_label(self):
        pass


class FakeClipboard:
    def __init__(self):
        self.text = None

    def setText(self, text):
        self.text = text


class FakeQApplication:
    clip = None

    @classmethod
    def clipboard(cls):
        return cls.clip


@pytest.fixture
def backend(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(input_backend, "_backend", fake)
    return fake


@pytest.fixture
def clipboard(monkeypatch):
    clip = FakeClipboard()
    FakeQApplication.clip = clip
    monkeypatch.setattr(delivery, "QApplication", FakeQApplication)
    return clip


# ---- the interface itself --------------------------------------------------


def test_delivery_names_no_operating_system():
    assert not hasattr(delivery, "win32_input")
    assert hasattr(delivery, "input_backend")


def test_backend_resolves_to_something_usable_on_this_machine():
    assert input_backend.active_backend_name()
    for op in ("inject_text", "paste_text", "backspaces", "select_all"):
        assert callable(getattr(input_backend, op))


def test_choose_injection_lives_in_the_shared_layer():
    assert input_backend.choose_injection("hi", paste_threshold=300) == "type"
    assert input_backend.choose_injection("x" * 301, paste_threshold=300) == "paste"


# ---- normal dictation ------------------------------------------------------


def test_short_dictation_is_typed_with_a_trailing_space(backend):
    d = delivery.TextDelivery(FakeApp())
    d.on_result("hello world")
    assert backend.ops == [("type", "hello world ")]


def test_long_dictation_is_pasted(backend):
    d = delivery.TextDelivery(FakeApp())
    d.on_result("x" * 400)
    assert backend.kinds == ["paste"]


def test_multiline_dictation_is_always_pasted(backend):
    d = delivery.TextDelivery(FakeApp())
    d.on_result("line one\nline two")
    assert backend.kinds == ["paste"]


def test_terminal_profile_types_even_long_text(backend):
    d = delivery.TextDelivery(FakeApp(profile={"verbatim": True}))
    d.on_result("x" * 400)
    assert backend.kinds == ["type"]


def test_force_paste_profile_pastes_short_text(backend):
    d = delivery.TextDelivery(FakeApp(profile={"force_paste": True}))
    d.on_result("hi")
    assert backend.kinds == ["paste"]


def test_whitespace_only_result_is_typed_never_pasted(backend):
    d = delivery.TextDelivery(FakeApp())
    d.on_result("\n")
    assert backend.ops == [("type", "\n")]


def test_empty_result_injects_nothing(backend):
    app = FakeApp()
    d = delivery.TextDelivery(app)
    d.on_result("")
    assert backend.ops == []
    assert "didnt_catch" in app.overlay.toasts


def test_failed_injection_parks_the_text_on_the_clipboard(monkeypatch, clipboard):
    fake = FakeBackend(paste_ok=False)
    monkeypatch.setattr(input_backend, "_backend", fake)
    app = FakeApp()
    d = delivery.TextDelivery(app)
    d.on_result("x" * 400)
    assert clipboard.text == "x" * 400
    assert "inject_failed" in app.overlay.toasts


def test_suspect_typed_injection_also_rescues_to_clipboard(monkeypatch, clipboard):
    fake = FakeBackend(type_ok=False)   # SendInput delivered fewer events
    monkeypatch.setattr(input_backend, "_backend", fake)
    app = FakeApp()
    d = delivery.TextDelivery(app)
    d.on_result("short one")
    assert clipboard.text == "short one"


# ---- voice-edit commands ---------------------------------------------------


def test_scratch_that_backspaces_the_last_injection(backend):
    d = delivery.TextDelivery(FakeApp())
    d.on_result("hello world")
    backend.ops.clear()
    d.run_voice_command(voice_commands.parse("scratch that"))
    assert backend.ops == [("backspace", len("hello world "))]
    assert d.last_injected_len == 0


def test_select_all_goes_through_the_interface(backend):
    d = delivery.TextDelivery(FakeApp())
    d.run_voice_command(voice_commands.parse("select all"))
    assert backend.ops == [("select_all", None)]


def test_replace_backspaces_then_reinjects(backend):
    d = delivery.TextDelivery(FakeApp())
    d.on_result("the cat sat")
    backend.ops.clear()
    d.run_voice_command(voice_commands.parse("replace cat with dog"))
    assert backend.kinds[0] == "backspace"
    assert ("type", "the dog sat ") in backend.ops
