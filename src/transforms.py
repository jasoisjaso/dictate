"""User-defined regex transforms applied to transcripts."""
import re


def apply_transforms(text: str, rules: list) -> str:
    """Apply a list of {find, replace} regex rules to text.

    Rules are applied in order. Matching is case-insensitive.
    """
    for rule in rules:
        pattern = rule.get("find", "")
        replacement = rule.get("replace", "")
        if pattern:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text
