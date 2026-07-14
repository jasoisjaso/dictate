"""Tests for auto_punctuation module."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from auto_punct import add_punctuation


def test_adds_period_at_end():
    assert add_punctuation("hello world") == "Hello world."


def test_capitalises_first_letter():
    assert add_punctuation("hello world.") == "Hello world."


def test_doesnt_double_punctuate():
    assert add_punctuation("hello world.") == "Hello world."


def test_preserves_existing_capitals():
    assert add_punctuation("Hello World") == "Hello World."


def test_handles_empty():
    assert add_punctuation("") == ""


def test_handles_already_capitalised():
    assert add_punctuation("Hello world") == "Hello world."


def test_preserves_question_mark():
    assert add_punctuation("what is this") == "What is this."


def test_preserves_exclamation():
    assert add_punctuation("wow") == "Wow."
