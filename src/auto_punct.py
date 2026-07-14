"""Auto-punctuation: add periods and capitalise without the user saying 'period'."""
import re


def add_punctuation(text: str) -> str:
    """Add a trailing period if missing and capitalise the first letter.

    This is the simple, no-cloud version: Whisper already adds punctuation
    in most cases when the model is large enough, but small/base models on
    CPU often produce unpunctuated text. This fills the gap.
    """
    if not text or not text.strip():
        return text
    text = text.strip()
    # Capitalise first letter
    if text[0].isalpha():
        text = text[0].upper() + text[1:]
    # Add trailing period if no terminal punctuation
    if not text[-1] in ".!?:":
        text = text + "."
    return text
