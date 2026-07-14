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


# ---- undo alias + format commands ---------------------------------------

def test_undo_alias():
    assert vc.parse("undo that") == vc.Command("scratch")
    assert vc.parse("undo") == vc.Command("scratch")
    assert vc.parse("undo last") == vc.Command("scratch")


def test_bold_command():
    cmd = vc.parse("bold that")
    assert cmd is not None
    assert cmd.kind == "format"
    assert cmd.mode == "bold"


def test_italic_command():
    cmd = vc.parse("italic that")
    assert cmd is not None
    assert cmd.kind == "format"
    assert cmd.mode == "italic"


def test_select_all_command():
    cmd = vc.parse("select all")
    assert cmd is not None
    assert cmd.kind == "format"
    assert cmd.mode == "select_all"


def test_format_not_triggered_by_prose():
    assert vc.parse("make that bold please") is None
    assert vc.parse("the bold text is important") is None


# ---- replace command -----------------------------------------------------

def test_replace_command():
    cmd = vc.parse("replace hello with hi")
    assert cmd is not None
    assert cmd.kind == "replace"
    assert cmd.old == "hello"
    assert cmd.new == "hi"

def test_replace_multiword():
    cmd = vc.parse("replace new york with los angeles")
    assert cmd is not None
    assert cmd.kind == "replace"
    assert cmd.old == "new york"
    assert cmd.new == "los angeles"

def test_replace_not_triggered_by_prose():
    assert vc.parse("please replace the battery") is None


# ---- Bosnian voice commands (ijekavian) --------------------------------

def test_bosnian_scratch():
    for s in ["obriši to", "poništi to", "poništi"]:
        cmd = vc.parse(s)
        assert cmd is not None
        assert cmd.kind == "scratch"

def test_bosnian_delete_word():
    cmd = vc.parse("obriši posljednju riječ")
    assert cmd is not None
    assert cmd.kind == "delete_words"
    assert cmd.n == 1

def test_bosnian_delete_two_words():
    cmd = vc.parse("obriši posljednje dvije riječi")
    assert cmd is not None
    assert cmd.kind == "delete_words"
    assert cmd.n == 2

def test_bosnian_delete_sentence():
    cmd = vc.parse("obriši posljednju rečenicu")
    assert cmd is not None
    assert cmd.kind == "delete_sentence"

def test_bosnian_bold():
    cmd = vc.parse("podebljaj")
    assert cmd is not None
    assert cmd.kind == "format"
    assert cmd.mode == "bold"

def test_bosnian_italic():
    cmd = vc.parse("iskosi")
    assert cmd is not None
    assert cmd.kind == "format"
    assert cmd.mode == "italic"

def test_bosnian_select_all():
    cmd = vc.parse("označi sve")
    assert cmd is not None
    assert cmd.kind == "format"
    assert cmd.mode == "select_all"

def test_bosnian_replace():
    cmd = vc.parse("zamijeni hello sa hi")
    assert cmd is not None
    assert cmd.kind == "replace"
    assert cmd.old == "hello"
    assert cmd.new == "hi"

def test_bosnian_serbian_not_confused():
    # Serbian ekavian forms should NOT trigger (poslednju = Serbian, posljednju = Bosnian)
    assert vc.parse("obriši poslednju reč") is None  # Serbian ekavian
