"""Tests for transforms module."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from transforms import apply_transforms


def test_simple_replace():
    rules = [{"find": "gonna", "replace": "going to"}]
    assert apply_transforms("I gonna go", rules) == "I going to go"


def test_regex_replace():
    rules = [{"find": r"\b(\w+)\s+\1\b", "replace": r"\1"}]
    assert apply_transforms("the the dog", rules) == "the dog"


def test_no_rules():
    assert apply_transforms("hello", []) == "hello"


def test_multiple_rules():
    rules = [
        {"find": "gonna", "replace": "going to"},
        {"find": "wanna", "replace": "want to"},
    ]
    assert apply_transforms("I gonna wanna go", rules) == "I going to want to go"


def test_case_insensitive():
    rules = [{"find": "GONNA", "replace": "going to"}]
    assert apply_transforms("I Gonna Go", rules) == "I going to Go"
