"""Voice editing commands — the difference between a transcriber and a tool.

The final transcript is checked against a small set of spoken *commands* that
operate on the text that was just injected, so you can fix things without
touching the keyboard:

    "scratch that"      -> delete the whole last dictation
    "delete last word"  -> delete just the last word (repeatable)
    "delete last N words"
    "capitalize that" / "capitalise that" -> Title-Case the last dictation
    "all caps that"     -> UPPERCASE the last dictation
    "lowercase that"    -> lowercase the last dictation
    "new line"/"new paragraph" already handled upstream as punctuation

A command only fires when the utterance is ONLY the command (nothing else was
said), so normal prose that happens to contain "delete" is never eaten.

The functions here are pure (no Win32) so they unit-test on any OS; the UI
layer turns a Command into the right backspace + re-inject calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# word-number words we accept in "delete last three words"
_NUMWORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


@dataclass
class Command:
    """A recognised voice-edit command.
    kind: scratch | delete_words | recase | redo_verbatim | delete_sentence | format | replace
    n:    word count for delete_words
    mode: 'upper' | 'lower' | 'title' for recase; 'bold'|'italic'|'select_all' for format
    old:  text to find (for replace)
    new:  replacement text (for replace)
    """
    kind: str
    n: int = 0
    mode: str = ""
    old: str = ""
    new: str = ""


def _norm(text: str) -> str:
    """Lowercase, strip punctuation/whitespace so 'Scratch that.' matches.
    Preserves Unicode letters (š, č, ć, đ, ž) for non-English commands."""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def parse(text: str) -> Command | None:
    """Return a Command if the WHOLE utterance is a voice-edit command, else None.

    Matching is deliberately strict (anchored to the whole string) so that a
    sentence like "please delete that file" is dictated normally, not treated
    as a command.
    """
    t = _norm(text)
    if not t:
        return None

    if t in ("scratch that", "delete that", "undo that", "scratch all"):
        return Command("scratch")

    # "delete/remove/scratch (the) last [N] word(s)"
    m = re.fullmatch(
        r"(?:delete|remove|scratch)(?: the)? last (?:(\d+|%s) )?words?"
        % "|".join(_NUMWORDS), t)
    if m:
        raw = m.group(1)
        if raw is None:
            n = 1
        elif raw.isdigit():
            n = int(raw)
        else:
            n = _NUMWORDS.get(raw, 1)
        return Command("delete_words", n=max(1, n))

    if t in ("capitalize that", "capitalise that", "title case that",
             "title case", "capitalize", "capitalise"):
        return Command("recase", mode="title")
    if t in ("all caps that", "all caps", "uppercase that", "uppercase"):
        return Command("recase", mode="upper")
    if t in ("lowercase that", "lower case that", "lowercase", "no caps"):
        return Command("recase", mode="lower")

    if t in ("redo that", "redo verbatim", "verbatim that", "raw that",
             "redo raw", "try again raw"):
        return Command("redo_verbatim")

    if t in ("delete last sentence", "delete sentence", "remove last sentence",
             "delete last line", "remove last line"):
        return Command("delete_sentence")

    if t in ("undo that", "undo last", "undo"):
        return Command("scratch")

    if t in ("bold that", "bold last", "bolden that"):
        return Command("format", mode="bold")
    if t in ("italic that", "italics that", "italicize that", "italicise that"):
        return Command("format", mode="italic")
    if t in ("select all", "select everything"):
        return Command("format", mode="select_all")

    # "replace X with Y" — find-and-replace in the last dictation
    m = re.fullmatch(r"replace (.+?) with (.+)", t)
    if m:
        return Command("replace", old=m.group(1), new=m.group(2))

    # Bosnian voice commands (ijekavian: posljednju, riječ, zamijeni)
    if t in ("obriši to", "poništi to", "poništi"):
        return Command("scratch")
    if t in ("obriši posljednju riječ", "obriši riječ",
             "obriši posljednju riječ"):
        return Command("delete_words", n=1)
    if t in ("obriši posljednju rečenicu", "obriši rečenicu"):
        return Command("delete_sentence")
    if t in ("obriši posljednje dvije riječi",):
        return Command("delete_words", n=2)
    if t in ("obriši posljednje tri riječi",):
        return Command("delete_words", n=3)
    # Bosnian formatting commands
    if t in ("podebljaj", "podebljaj to"):
        return Command("format", mode="bold")
    if t in ("iskosi", "iskosi to", "kurziv"):
        return Command("format", mode="italic")
    if t in ("označi sve", "oznaci sve"):
        return Command("format", mode="select_all")
    # Bosnian replace: "zamijeni X sa Y" or "zamijeni X sa y"
    m = re.fullmatch(r"zamijeni (.+?) sa (.+)", t)
    if m:
        return Command("replace", old=m.group(1), new=m.group(2))

    return None


def apply_recase(text: str, mode: str) -> str:
    if mode == "upper":
        return text.upper()
    if mode == "lower":
        return text.lower()
    if mode == "title":
        # Title-Case but keep small words readable; simple .title() is fine
        # for the "capitalize that" use case (names, headings).
        return text.title()
    return text


def tail_word_len(text: str, n: int) -> int:
    """How many characters to backspace to remove the last `n` words of `text`,
    INCLUDING any trailing space we injected. Whitespace between words is
    counted so "hello  world " -> deleting 1 word removes "world " etc.
    """
    if not text or n <= 0:
        return 0
    s = text.rstrip()                 # ignore the trailing space we add on inject
    removed = len(text) - len(s)      # trailing space(s) always go
    words = 0
    i = len(s)
    while i > 0 and words < n:
        # skip the word
        j = i
        while j > 0 and not s[j - 1].isspace():
            j -= 1
        removed += i - j
        words += 1
        # skip the whitespace before it (this becomes the new trailing gap)
        k = j
        while k > 0 and s[k - 1].isspace():
            k -= 1
        # only consume the gap if there are still more words to delete after,
        # so we don't chew into the previous surviving word's trailing space
        if words < n:
            removed += j - k
        i = k if words < n else j
    return removed
