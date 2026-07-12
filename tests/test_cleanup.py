import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import cleanup


def test_removes_standalone_fillers():
    assert cleanup.strip_fillers("So um I think uh yeah we ship") == "So I think yeah we ship"


def test_keeps_words_containing_filler_substring():
    # "umbrella" must survive
    assert cleanup.strip_fillers("Grab an umbrella") == "Grab an umbrella"


def test_dictionary_applies_whole_word_casefold():
    d = {"hello acrylic": "Hello Acrylic", "woolies": "Woolworths"}
    assert cleanup.apply_dictionary("i work at woolies", d) == "i work at Woolworths"


def test_dictionary_leaves_partial_matches():
    assert cleanup.apply_dictionary("wooliesworth", {"woolies": "Woolworths"}) == "wooliesworth"


def test_clean_combines_both():
    out = cleanup.clean("um i love woolies", remove_fillers=True,
                        dictionary={"woolies": "Woolworths"})
    assert out == "i love Woolworths"


def test_ollama_polish_fails_open(monkeypatch):
    # network exploding must return the input unchanged
    def boom(*a, **k):
        raise OSError("no ollama")
    monkeypatch.setattr(cleanup, "_ollama_generate", boom)
    assert cleanup.ollama_polish("hello there", "hermes4", "http://127.0.0.1:11434") == "hello there"


# ---- custom filler words (the "added a filler, relaunch, gone" bug) --------

def test_custom_filler_single_word():
    rx = cleanup._build_filler_re(cleanup.FILLERS + ["like", "basically"])
    assert cleanup.strip_fillers("I like basically went there", rx) == "I went there"


def test_custom_filler_multiword():
    rx = cleanup._build_filler_re(cleanup.FILLERS + ["you know"])
    assert cleanup.strip_fillers("So you know we ship it", rx) == "So we ship it"


def test_custom_filler_multiword_tolerates_extra_spacing():
    rx = cleanup._build_filler_re(["you know"])
    assert cleanup.strip_fillers("well you  know maybe", rx) == "well maybe"


def test_custom_filler_is_whole_word_only():
    rx = cleanup._build_filler_re(["like"])
    # "likely" must survive
    assert cleanup.strip_fillers("that is likely true", rx) == "that is likely true"


def test_blank_and_empty_fillers_never_match_everything():
    # a stray blank entry must NOT compile to a match-anything regex
    rx = cleanup._build_filler_re(["", "  ", None])
    assert cleanup.strip_fillers("nothing should be stripped here", rx) == \
        "nothing should be stripped here"


def test_empty_list_is_a_noop():
    rx = cleanup._build_filler_re([])
    assert cleanup.strip_fillers("um keep everything um", rx) == "um keep everything um"


def test_default_strip_fillers_unchanged_without_custom():
    # regression: builtin behaviour when no custom regex passed
    assert cleanup.strip_fillers("So um I think uh yeah") == "So I think yeah"


# ---- silence-hallucination guard ------------------------------------------

def test_known_hallucinations_flagged():
    for s in ["Thank you.", "Thanks for watching!", "Please subscribe",
              "you", "Bye.", "  Thank you very much.  "]:
        assert cleanup.is_probable_hallucination(s), s


def test_real_short_sentences_not_flagged():
    # whole-string match only — a real short sentence must survive
    for s in ["Thank you Sarah", "please subscribe to the newsletter today",
              "buy milk", "the cat sat", "thanks for the report Dave"]:
        assert not cleanup.is_probable_hallucination(s), s


def test_empty_is_hallucination():
    assert cleanup.is_probable_hallucination("")
    assert cleanup.is_probable_hallucination("   ")
