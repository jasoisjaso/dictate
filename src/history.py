"""In-memory dictation history (newest first, bounded).

Optionally persisted to disk as JSON when persist_path is set.
Off by default: the privacy promise is that nothing you say is recorded.
When persistence is enabled, history lives in a JSON file the user can
delete at any time.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field


@dataclass
class Entry:
    text: str
    app: str | None = None
    when: str = field(default_factory=lambda: time.strftime("%H:%M"))


class History:
    def __init__(self, limit: int = 25, persist_path: str | None = None):
        self.limit = limit
        self._persist_path = persist_path
        self._items: list[Entry] = []
        if persist_path:
            self._load()

    def _load(self):
        """Load from JSON file if it exists."""
        try:
            with open(self._persist_path, encoding="utf-8") as f:
                data = json.load(f)
                self._items = [Entry(**e) for e in data]
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            pass

    def _save(self):
        """Save to JSON file."""
        if not self._persist_path:
            return
        try:
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump([{"text": e.text, "app": e.app, "when": e.when}
                           for e in self._items], f, ensure_ascii=False)
        except Exception:
            pass

    def add(self, text: str, app: str | None = None):
        if not text or not text.strip():
            return
        self._items.insert(0, Entry(text=text, app=app))
        del self._items[self.limit:]
        self._save()

    def items(self) -> list[Entry]:
        return list(self._items)

    def clear(self):
        self._items.clear()
        self._save()
