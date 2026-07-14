import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import voice_commands as vc  # noqa: E402


# ---- parse: only whole-utterance commands fire ----------------------------

def test_scratch_variants():
    for s in ["scratch that", "Scratch that.", "delete that", "undo that"]:
        assert vc.parse(s) == vc.Command("scratch")


def test_prose_is_not_a_command():
    # these contain command-ish words but are normal speech -> None
    for s in ["please delete that file", "scratch the surface a little",
              "I need to capitalize on this", "the last word is important"]:
        assert vc.parse(s) is None


def test_delete_last_word_default_one():
    assert vc.parse("delete last word") == vc.Command("delete_words", n=1)


def test_delete_last_n_words_digit_and_word():
    assert vc.parse("delete last 3 words") == vc.Command("delete_words", n=3)
    assert vc.parse("delete the last three words") == vc.Command("delete_words", n=3)
    assert vc.parse("remove last two words") == vc.Command("delete_words", n=2)


def test_recase_commands():
    assert vc.parse("capitalize that").mode == "title"
    assert vc.parse("capitalise that").mode == "title"
    assert vc.parse("all caps that").mode == "upper"
    assert vc.parse("lowercase that").mode == "lower"


def test_apply_recase():
    assert vc.apply_recase("hello world", "upper") == "HELLO WORLD"
    assert vc.apply_recase("HELLO", "lower") == "hello"
    assert vc.apply_recase("hello world", "title") == "Hello World"


# ---- tail_word_len: the backspace char-math (the risky part) --------------

def test_tail_one_word_with_trailing_space():
    # we inject "hello world " (trailing space); deleting 1 word removes "world "
    assert vc.tail_word_len("hello world ", 1) == len("world ")


def test_tail_two_words():
    # deleting 2 words from "hello there world " removes "there world "
    assert vc.tail_word_len("hello there world ", 2) == len("there world ")


def test_tail_all_words_removes_everything():
    assert vc.tail_word_len("hello world ", 5) == len("hello world ")


def test_tail_no_trailing_space():
    assert vc.tail_word_len("hello world", 1) == len("world")


def test_tail_empty():
    assert vc.tail_word_len("", 3) == 0
    assert vc.tail_word_len("word", 0) == 0


# ---- redo_verbatim command -----------------------------------------------

def test_redo_verbatim_variants():
    for s in ["redo that", "redo verbatim", "verbatim that", "raw that",
              "redo raw", "try again raw"]:
        cmd = vc.parse(s)
        assert cmd is not None
        assert cmd.kind == "redo_verbatim"


def test_redo_verbatim_not_triggered_by_prose():
    assert vc.parse("redo that last step") is None
    assert vc.parse("I want to redo the whole thing") is None


# ---- delete_sentence command --------------------------------------------

def test_delete_sentence_variants():
    for s in ["delete last sentence", "delete sentence",
              "remove last sentence", "delete last line", "remove last line"]:
        cmd = vc.parse(s)
        assert cmd is not None
        assert cmd.kind == "delete_sentence"


def test_delete_sentence_not_triggered_by_prose():
    assert vc.parse("delete that sentence from the document") is None
    assert vc.parse("the last sentence was important") is None
