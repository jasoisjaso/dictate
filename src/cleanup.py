"""Offline transcript cleanup: filler removal + personal dictionary.
Optional local-LLM polish via Ollama (off by default, fail-open)."""
from __future__ import annotations

import json
import logging
import re
import urllib.request

log = logging.getLogger("dictate.cleanup")

FILLERS = [
    # English hesitation sounds — safe to strip in any language
    "um", "uh", "erm", "uhh", "umm", "er", "ah",
]

# Bosnian/Croatian/Serbian hesitation sounds. ONLY pure hesitations belong
# here. Words like "pa", "ma", "e", "ono", "znaci", "dakle" are REAL words
# used constantly in normal Bosnian sentences — stripping them mangles long
# dictations (words silently disappear mid-sentence). If a user wants those
# gone they can add them via custom_fillers explicitly.
FILLERS_BS = ["ovaj", "hm", "hmm", "mhm", "aha", "eee"]


def default_fillers(language: str | None = None) -> list[str]:
    """Built-in filler list appropriate for the configured language."""
    out = list(FILLERS)
    if (language or "").lower() in ("bs", "hr", "sr"):
        out += FILLERS_BS
    return out

# Phrases faster-whisper/Whisper confidently emits on silence or near-silent
# audio (the infamous "no speech -> subscribe" hallucinations). If the WHOLE
# transcript is just one of these, it's almost certainly a hallucination on an
# empty take, so we drop it rather than typing it into the user's document.
# Kept lowercase, punctuation-stripped for comparison.
_HALLUCINATION_PHRASES = frozenset({
    "thank you", "thank you.", "thanks for watching", "thanks for watching!",
    "thank you for watching", "thank you for watching!", "please subscribe",
    "please subscribe.", "subscribe", "like and subscribe",
    "thanks for watching!", "you", "bye", "bye.", "okay", "ok",
    "so", ".", "..", "...", "mm", "mhm", "hmm", "yeah", "the",
    "thank you very much", "thank you very much.", "thank you.",
    "thank you for watching.", "please subscribe to my channel",
    "thanks", "thanks.", "i'm sorry", "i'm sorry.",
})


def is_probable_hallucination(text: str) -> bool:
    """True if `text` is almost certainly a silence hallucination (the whole
    transcript is a single known filler phrase). Only fires on WHOLE-string
    matches so real short sentences ("Thank you, Sarah") are never dropped."""
    if not text:
        return True
    norm = re.sub(r"[^a-z' ]", "", text.lower()).strip()
    norm = re.sub(r"\s+", " ", norm)
    if not norm:
        return True  # nothing but whitespace/punctuation -> treat as empty
    return norm in _HALLUCINATION_PHRASES


def _build_filler_re(words):
    """Compile a whole-word, case-insensitive filler matcher from `words`.
    Multi-word entries (e.g. "you know", "sort of") are supported. Empty /
    blank entries are ignored so a stray blank row can never blow up the regex
    (an empty alternative would otherwise match at every position)."""
    cleaned = []
    seen = set()
    for w in words or ():
        w = (w or "").strip()
        if not w:
            continue
        low = w.lower()
        if low in seen:
            continue
        seen.add(low)
        # allow internal runs of whitespace in multi-word fillers to match any
        # spacing whisper produced ("you know" vs "you  know")
        cleaned.append(r"\s+".join(map(re.escape, w.split())))
    if not cleaned:
        # nothing to strip -> a regex that never matches
        return re.compile(r"(?!x)x")
    # longest first so "you know" wins over a bare "you" if both are present
    cleaned.sort(key=len, reverse=True)
    return re.compile(r"\b(?:%s)\b[ ,]*" % "|".join(cleaned), re.IGNORECASE)


_FILLER_RE = _build_filler_re(FILLERS)

_POLISH_PROMPT = (
    "Fix grammar and punctuation of this dictated text. Keep the meaning, "
    "wording and tone; do not add or remove information; do not answer "
    "questions in the text. Return ONLY the corrected text.\n\nText: "
)


def strip_fillers(text: str, filler_re: "re.Pattern | None" = None) -> str:
    rx = filler_re if filler_re is not None else _FILLER_RE
    out = rx.sub(" ", text)
    # collapse runs of spaces/tabs ONLY — newlines from spoken "new line"
    # commands must survive this pass
    out = re.sub(r"[ \t]{2,}", " ", out)
    return re.sub(r" *\n *", "\n", out).strip()


def apply_dictionary(text: str, mapping: dict[str, str]) -> str:
    # longest keys first so multi-word entries win
    for key in sorted(mapping, key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(key)}\b", mapping[key], text,
                      flags=re.IGNORECASE)
    return text


def clean(text: str, *, remove_fillers: bool,
          dictionary: dict[str, str] | None,
          filler_re: "re.Pattern | None" = None) -> str:
    if remove_fillers:
        text = strip_fillers(text, filler_re)
    if dictionary:
        text = apply_dictionary(text, dictionary)
    return text


# ---- optional local-LLM polish (never blocks dictation) -----------------

def _ollama_generate(prompt: str, model: str, endpoint: str,
                     timeout: float) -> str:
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/api/generate",
        data=json.dumps({"model": model, "prompt": prompt,
                         "stream": False}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read()).get("response", "").strip()


def ollama_polish(text: str, model: str, endpoint: str,
                  timeout: float = 4.0, tone: str | None = None) -> str:
    """Grammar/punctuation pass through a local Ollama model.
    tone ("casual"/"professional") adapts phrasing to the target app.
    Fail-open: any error or empty answer returns the original text."""
    if not text.strip():
        return text
    prompt = _POLISH_PROMPT
    if tone:
        prompt = prompt.replace(
            "Fix grammar and punctuation",
            f"Fix grammar and punctuation and keep a {tone} register")
    try:
        out = _ollama_generate(prompt + text, model, endpoint, timeout)
        return out if out else text
    except Exception as ex:
        log.debug("ollama polish unavailable (%s); using raw text", ex)
        return text
