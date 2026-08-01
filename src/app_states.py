"""Shared app-state and dictation-mode constants.

Lives in its own tiny module so the tray shell, session controller and
delivery paths can all import them without touching (or circularly
importing) the ui coordinator.
"""

LOADING, IDLE, RECORDING, TRANSCRIBING = "loading", "idle", "recording", "transcribing"

STATE_COLOR = {
    LOADING: "#8a939b",
    IDLE: "#46c07a",
    RECORDING: "#e05252",
    TRANSCRIBING: "#4da3ff",
}

# Dictation modes — cycle with the mode_cycle_key (default F7).
# "auto" means: use per-app profile detection (the existing behaviour).
MODE_NAMES = ["auto", "prose", "code", "email"]
MODE_LABELS = {
    "auto": "Auto",
    "prose": "Prose",
    "code": "Code",
    "email": "Email",
}
