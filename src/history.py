"""In-memory dictation history (newest first, bounded).

Deliberately NOT persisted to disk: the privacy promise is that nothing you
say is recorded. History exists so a transcription that landed in the wrong
window isn't lost — it lives until the app closes, then it's gone.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Entry:
    text: str
    app: str | None = None
    when: str = field(default_factory=lambda: time.strftime("%H:%M"))


class History:
    def __init__(self, limit: int = 25):
        self.limit = limit
        self._items: list[Entry] = []

    def add(self, text: str, app: str | None = None):
        if not text or not text.strip():
            return
        self._items.insert(0, Entry(text=text, app=app))
        del self._items[self.limit:]

    def items(self) -> list[Entry]:
        return list(self._items)

    def clear(self):
        self._items.clear()
