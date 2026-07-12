import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import history


def test_newest_first_and_bounded():
    h = history.History(limit=3)
    for i in range(5):
        h.add(f"entry {i}", app="notepad.exe")
    items = h.items()
    assert len(items) == 3
    assert items[0].text == "entry 4"
    assert items[-1].text == "entry 2"


def test_empty_text_not_stored():
    h = history.History()
    h.add("", app=None)
    h.add("   ", app=None)
    assert h.items() == []


def test_entry_has_timestamp_and_app():
    h = history.History()
    h.add("hello", app="Discord.exe")
    e = h.items()[0]
    assert e.app == "Discord.exe"
    assert e.when  # non-empty HH:MM string
