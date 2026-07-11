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
