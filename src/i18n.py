"""UI translations. English is the source of truth; Bosnian is the first
translation. ui_language in [ui] config: "auto" follows the dictation
language, "en"/"bs" force it.

Keep keys short and flat. Every key MUST exist in EN; translations fall
back to EN per-key so a missing translation can never crash or blank the UI.
"""
from __future__ import annotations

EN = {
    # tray
    "loading": "Loading model...",
    "ready": "Ready",
    "listening": "Listening...",
    "transcribing": "Transcribing...",
    "copy_last": "Copy last dictation",
    "settings": "Settings...",
    "history": "History...",
    "guide": "How to use...",
    "quit": "Quit",
    "mode": "Mode",
    "cycle_hint": "to cycle",
    "hold_and_talk": "Hold {key} and talk",
    "tap_to_talk": "Tap {key} to talk",
    "ready_balloon": "{model} on {device}. {hint}.",
    "ready_title": "Dictate ready",
    "update_title": "Dictate, update available",
    "update_body": "Version {tag} is out. Click here to download.",
    "crash_title": "Dictate recovered from a crash",
    # toasts
    "didnt_catch": "didn't catch that",
    "still_loading": "still loading, ready in a moment",
    "finishing": "finishing the last one...",
    "copied_last": "copied last dictation",
    "nothing_yet": "nothing dictated yet",
    "scratched": "scratched",
    "paused": "paused",
    "resumed": "resumed",
    "too_long": "that took too long, try a shorter take",
    "words_undo": "{n} words · {undo}",
    "word_undo": "1 word · {undo}",
    "undo_hint": "Ctrl+Z to undo",
    "undo_hint_term": "say 'scratch that' to undo",
    "inject_failed": "couldn't type there, text copied, press Ctrl+V",
    "deleted_words": "deleted {n} words",
    "deleted_word": "deleted 1 word",
    "deleted_sentence": "deleted last sentence",
    "selected_all": "selected all",
    "nothing_to_change": "nothing to change",
    "redone": "redone verbatim",
    "nothing_to_redo": "nothing to redo",
    "no_mic": "no microphone detected, check Settings",
}

BS = {
    # tray
    "loading": "Učitavanje modela...",
    "ready": "Spremno",
    "listening": "Slušam...",
    "transcribing": "Prepisujem...",
    "copy_last": "Kopiraj zadnji diktat",
    "settings": "Postavke...",
    "history": "Historija...",
    "guide": "Kako se koristi...",
    "quit": "Izlaz",
    "mode": "Način",
    "cycle_hint": "za promjenu",
    "hold_and_talk": "Drži {key} i govori",
    "tap_to_talk": "Pritisni {key} i govori",
    "ready_balloon": "{model} na {device}. {hint}.",
    "ready_title": "Dictate je spreman",
    "update_title": "Dictate, dostupna je nova verzija",
    "update_body": "Izašla je verzija {tag}. Klikni ovdje za preuzimanje.",
    "crash_title": "Dictate se oporavio od pada",
    # toasts
    "didnt_catch": "nisam razumio, pokušaj ponovo",
    "still_loading": "još se učitava, samo trenutak",
    "finishing": "završavam prethodni...",
    "copied_last": "zadnji diktat kopiran",
    "nothing_yet": "još ništa nije diktirano",
    "scratched": "obrisano",
    "paused": "pauzirano",
    "resumed": "nastavljeno",
    "too_long": "predugo je trajalo, pokušaj kraće",
    "words_undo": "{n} riječi · {undo}",
    "word_undo": "1 riječ · {undo}",
    "undo_hint": "Ctrl+Z za poništavanje",
    "undo_hint_term": "reci 'obriši to' za poništavanje",
    "inject_failed": "nisam mogao unijeti tekst, kopiran je, pritisni Ctrl+V",
    "deleted_words": "obrisano {n} riječi",
    "deleted_word": "obrisana 1 riječ",
    "deleted_sentence": "obrisana zadnja rečenica",
    "selected_all": "sve označeno",
    "nothing_to_change": "nema šta da se mijenja",
    "redone": "ponovljeno doslovno",
    "nothing_to_redo": "nema šta da se ponovi",
    "no_mic": "mikrofon nije pronađen, provjeri Postavke",
}

_TABLES = {"en": EN, "bs": BS}


def resolve_ui_language(cfg: dict) -> str:
    """[ui].language: auto | en | bs. auto follows the dictation language
    (bs/hr/sr all read Bosnian comfortably)."""
    want = str(cfg.get("ui", {}).get("language", "auto")).strip().lower()
    if want in _TABLES:
        return want
    dict_lang = (cfg.get("whisper", {}).get("language") or "en").lower()
    return "bs" if dict_lang in ("bs", "hr", "sr") else "en"


class Translator:
    """t("key", n=3) -> localized string with {placeholders} filled.
    Missing key or bad placeholder falls back to English, then to the key."""

    def __init__(self, lang: str = "en"):
        self.lang = lang if lang in _TABLES else "en"

    def __call__(self, _key: str, **kwargs) -> str:
        for table in (_TABLES[self.lang], EN):
            if _key in table:
                try:
                    return table[_key].format(**kwargs) if kwargs else table[_key]
                except (KeyError, IndexError):
                    continue
        return _key
