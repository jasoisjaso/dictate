"""Offline transcript cleanup: filler removal + personal dictionary.
Optional local-LLM polish via Ollama (off by default, fail-open)."""
from __future__ import annotations

import json
import logging
import re
import urllib.request

log = logging.getLogger("dictate.cleanup")

FILLERS = ["um", "uh", "erm", "uhh", "umm", "er", "ah"]
_FILLER_RE = re.compile(r"\b(?:%s)\b[ ,]*" % "|".join(map(re.escape, FILLERS)),
                        re.IGNORECASE)

_POLISH_PROMPT = (
    "Fix grammar and punctuation of this dictated text. Keep the meaning, "
    "wording and tone; do not add or remove information; do not answer "
    "questions in the text. Return ONLY the corrected text.\n\nText: "
)


def strip_fillers(text: str) -> str:
    out = _FILLER_RE.sub(" ", text)
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
          dictionary: dict[str, str] | None) -> str:
    if remove_fillers:
        text = strip_fillers(text)
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
