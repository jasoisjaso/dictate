"""Accessibility Permission preflight (ticket 05).

macOS attaches the Accessibility grant to a *binary identity*, and without it
the operating system drops both directions silently: posted keyboard events go
nowhere and event-tap observations never arrive. No exception is raised, so
Dictate looks alive while the Trigger never fires and Injection does nothing.
The app has to notice and say so itself.

The seams are pure — every decision takes the platform and the probe result as
arguments — so Windows can test the macOS answers and vice versa:

    needs_accessibility_prompt(system, trusted) -> bool
    settings_pane_url()                         -> System Settings deep link
    permission_summary(system, trusted)         -> one line for the log
    preflight(system=, trusted=)                -> PermissionState
    run_preflight(...)                          -> the whole startup step

Only `accessibility_trusted()` and `open_settings_pane()` touch the real
machine, and neither raises: a permission check that crashes the app is worse
than the missing permission.
"""

import logging
import platform
from dataclasses import dataclass

log = logging.getLogger("dictate.permissions")

MACOS = "Darwin"

# The Accessibility list in System Settings > Privacy & Security. The
# com.apple.preference.security anchor is the old pane id, still honoured by
# the Settings app on Ventura and later.
SETTINGS_PANE_URL = (
    "x-apple.systempreferences:com.apple.preference.security"
    "?Privacy_Accessibility"
)

PROMPT_MESSAGE = (
    "Dictate needs Accessibility permission.\n\n"
    "macOS blocks it silently without the grant: the push-to-talk key is "
    "never seen, so recording never starts, and finished text cannot be "
    "typed into the app you are working in.\n\n"
    "Open Privacy & Security > Accessibility, switch Dictate on, then "
    "restart Dictate."
)


@dataclass(frozen=True)
class PermissionState:
    """What startup learned about the grant.

    ok            — nothing is blocking Injection or the Trigger
    should_prompt — show the dialog before the tray comes up
    message       — what the dialog says; explains the consequence, not just
                    the word "permission"
    url           — the pane the dialog's button opens ("" when not macOS)
    summary       — the line written to the log, so a bug report identifies
                    the permission state without a screenshot
    """

    ok: bool
    should_prompt: bool
    message: str
    url: str
    summary: str


def is_macos(system: str | None = None) -> bool:
    return (system or platform.system()) == MACOS


def settings_pane_url() -> str:
    return SETTINGS_PANE_URL


def _ax_is_process_trusted():
    """The AXIsProcessTrusted symbol, wherever pyobjc is exposing it.

    It belongs to HIServices, which ApplicationServices re-exports. It is NOT
    in Quartz — pyobjc's lazy loader raises AttributeError there — so ask the
    frameworks that actually define it, newest binding first.
    """
    last = None
    for module_name in ("ApplicationServices", "HIServices", "Quartz"):
        try:
            mod = __import__(module_name)
            return getattr(mod, "AXIsProcessTrusted")
        except Exception as ex:  # missing framework or missing symbol
            last = ex
    raise last if last else AttributeError("AXIsProcessTrusted")


def accessibility_trusted(system: str | None = None) -> bool:
    """Whether this process may post and observe keyboard events.

    True everywhere but macOS — there is no such gate on Windows or Linux, and
    reporting False there would block a working app for no reason.
    """
    if not is_macos(system):
        return True
    try:
        return bool(_ax_is_process_trusted()())
    except Exception:
        # pyobjc missing or the symbol moved: assume the worst on macOS, since
        # the visible symptom of a genuinely missing grant is "nothing at all
        # happens" and the user deserves the explanation either way.
        log.debug("AXIsProcessTrusted unavailable", exc_info=True)
        return False


def open_settings_pane(system: str | None = None, _run=None) -> bool:
    """Open System Settings on the Accessibility list. True if it was asked.

    `open` is the only supported way to hand a URL scheme to the Settings app;
    it returns before Settings finishes launching, so a True here means "the
    request was made", not "the pane is on screen". Failure is reported rather
    than raised — the dialog already names the pane in words, so a button that
    cannot launch Settings must not take the app down with it.
    """
    if not is_macos(system):
        return False
    run = _run
    if run is None:
        import subprocess
        run = subprocess.run
    try:
        run(["open", settings_pane_url()], check=False, timeout=10)
        return True
    except Exception:
        log.warning("could not open the Accessibility pane", exc_info=True)
        return False


def needs_accessibility_prompt(system: str | None = None,
                               trusted: bool | None = None) -> bool:
    """Only macOS, only when the grant is actually missing."""
    if not is_macos(system):
        return False
    if trusted is None:
        trusted = accessibility_trusted(system)
    return not trusted


def permission_summary(system: str | None = None,
                       trusted: bool | None = None) -> str:
    if not is_macos(system):
        return "accessibility permission: not applicable on this platform"
    if trusted is None:
        trusted = accessibility_trusted(system)
    return ("accessibility permission: granted" if trusted
            else "accessibility permission: MISSING — hotkeys and typing "
                 "will do nothing")


def preflight(system: str | None = None,
              trusted: bool | None = None) -> PermissionState:
    """The startup decision, in one value.

    Callers log `summary` unconditionally and show `message` with a button to
    `url` when `should_prompt`.
    """
    system = system or platform.system()
    if trusted is None:
        trusted = accessibility_trusted(system)
    prompt = needs_accessibility_prompt(system, trusted)
    return PermissionState(
        ok=not prompt,
        should_prompt=prompt,
        message=PROMPT_MESSAGE if prompt else "",
        url=settings_pane_url() if is_macos(system) else "",
        summary=permission_summary(system, trusted),
    )


def _qt_ask(state: PermissionState) -> bool:
    """The default dialog. Imported here so the module stays importable — and
    testable — on a machine with no Qt and no display."""
    from PySide6.QtWidgets import QMessageBox

    box = QMessageBox()
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("Dictate needs permission")
    box.setText(state.message)
    open_btn = box.addButton("Open Settings", QMessageBox.AcceptRole)
    box.addButton("Later", QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is open_btn


def run_preflight(system: str | None = None, trusted: bool | None = None,
                  ask=None, opener=None, log_line=None) -> bool:
    """The whole startup step: log the state, and explain it if it is wrong.

    Returns whether the grant is in place. Dictate starts either way — the
    user may grant it from the still-open Settings pane and restart, and a
    hard exit would strand them with no window to try again from.

    `ask` and `opener` are seams, so the decision path is testable without a
    display; both default to the real dialog and the real `open`.
    """
    state = preflight(system, trusted)
    (log_line or log.info)(state.summary)
    if not state.should_prompt:
        return state.ok
    try:
        if (ask or _qt_ask)(state):
            (opener or (lambda: open_settings_pane(system)))()
    except Exception:
        # No Qt, no display, a theming crash — none of it may stop startup:
        # the app still works for anyone who does have the grant.
        log.warning("could not show the Accessibility prompt", exc_info=True)
    return state.ok
