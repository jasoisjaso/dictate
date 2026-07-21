"""Tests for v1.3.0: cleanup levels, Bosnian voice pack, i18n, injection
safety net."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cleanup
import i18n
import lang_bs
import voice_commands
from engine import WhisperTranscriber, _build_lexicon
from win32_input import injection_suspect

BASE = {"whisper": {"model_size": "small", "device": "cpu",
                    "compute_type": "int8"}}


def _eng(level=None, lang="en", **extra_cfg):
    cfg = {"whisper": {**BASE["whisper"], "language": lang}, **extra_cfg}
    if level is not None:
        cfg["cleanup"] = {**cfg.get("cleanup", {}), "level": level}
    return WhisperTranscriber(cfg)


# ---- cleanup levels ---------------------------------------------------------

def test_level_off_keeps_fillers_and_case():
    assert _eng("off").post_process("um hello world") == "um hello world"


def test_level_light_strips_fillers_no_casing():
    out = _eng("light").post_process("um hello world")
    assert "um" not in out
    assert out.startswith("hello")  # no sentence-casing at light


def test_level_light_applies_dictionary():
    e = _eng("light", dictionary={"woolies": "Woolworths"})
    assert "Woolworths" in e.post_process("um i love woolies today")


def test_level_standard_is_current_default():
    out = _eng("standard").post_process("um hello world")
    assert out.startswith("Hello")


def test_default_level_is_standard():
    assert _eng().cleanup_level == "standard"


def test_unknown_level_falls_back_to_standard():
    assert _eng("bananas").cleanup_level == "standard"


def test_level_high_without_ollama_matches_standard():
    # high with no reachable Ollama must degrade to standard, not break
    e = _eng("high")
    assert e.ollama_available is False
    assert e.post_process("um hello world").startswith("Hello")


def test_punctuation_still_works_at_light():
    out = _eng("light").post_process("hello comma world period")
    assert "," in out and "." in out


# ---- Bosnian voice pack -----------------------------------------------------

def test_bs_lexicon_included_for_bosnian():
    phrases = [p for p, _ in _build_lexicon("bs")]
    assert "tačka" in phrases and "novi red" in phrases


def test_bs_lexicon_excluded_for_german():
    phrases = [p for p, _ in _build_lexicon("de")]
    assert "tačka" not in phrases
    assert "period" in phrases


def test_bs_lexicon_included_for_auto():
    phrases = [p for p, _ in _build_lexicon(None)]
    assert "tačka" in phrases


def test_ascii_fallback_tacka():
    # Whisper sometimes drops diacritics; "tacka" must still work
    out = _eng("standard", lang="bs").post_process("zdravo tacka")
    assert out.rstrip().endswith(".")


def test_znak_pitanja_multiword():
    out = _eng("standard", lang="bs").post_process("jesi li tu znak pitanja")
    assert out.rstrip().endswith("?")


def test_bs_anchor_prompt_set():
    assert "ijekavicom" in _eng(lang="bs").initial_prompt


def test_bs_anchor_disabled_by_config():
    e = WhisperTranscriber({"whisper": {**BASE["whisper"], "language": "bs",
                                        "bs_anchor": False}})
    assert e.initial_prompt is None


def test_en_engine_has_no_bs_anchor():
    assert _eng(lang="en").initial_prompt is None


def test_user_prompt_beats_anchor():
    e = WhisperTranscriber({"whisper": {**BASE["whisper"], "language": "bs",
                                        "initial_prompt": "Moj tekst."}})
    assert e.initial_prompt == "Moj tekst."


def test_bs_hallucinations_ascii_folded():
    assert cleanup.is_probable_hallucination("Hvala na gledanju",
                                             lang_bs.HALLUCINATIONS)
    # real short Bosnian sentence must survive
    assert not cleanup.is_probable_hallucination("hvala ti brate za sve",
                                                 lang_bs.HALLUCINATIONS)


def test_bs_commands_from_pack():
    cmd = voice_commands.parse("Obriši to.")
    assert cmd is not None and cmd.kind == "scratch"
    cmd = voice_commands.parse("obrisi posljednju rijec")  # ASCII fallback
    assert cmd is not None and cmd.kind == "delete_words" and cmd.n == 1
    cmd = voice_commands.parse("velika slova")
    assert cmd is not None and cmd.kind == "recase" and cmd.mode == "upper"
    cmd = voice_commands.parse("ponovi doslovno")
    assert cmd is not None and cmd.kind == "redo_verbatim"


def test_bs_replace_ekavian_variant():
    cmd = voice_commands.parse("zameni pas sa mačka")
    assert cmd is not None and cmd.kind == "replace"
    assert cmd.old == "pas" and cmd.new == "mačka"


def test_bs_fillers_via_pack():
    fillers = cleanup.default_fillers("bs")
    assert "ovaj" in fillers and "um" in fillers
    assert "pa" not in fillers  # real word, never a filler


# ---- i18n -------------------------------------------------------------------

def test_translator_bs_basic():
    t = i18n.Translator("bs")
    assert t("ready") == "Spremno"
    assert t("quit") == "Izlaz"


def test_translator_en_default():
    t = i18n.Translator("en")
    assert t("ready") == "Ready"


def test_translator_placeholders():
    t = i18n.Translator("bs")
    out = t("hold_and_talk", key="Right Ctrl")
    assert "Right Ctrl" in out and "Drži" in out


def test_translator_missing_key_returns_key():
    assert i18n.Translator("bs")("no_such_key_xyz") == "no_such_key_xyz"


def test_translator_unknown_lang_falls_back_en():
    assert i18n.Translator("fr")("ready") == "Ready"


def test_every_bs_key_exists_in_en():
    # BS may not invent keys that EN lacks (EN is the schema)
    assert set(i18n.BS) <= set(i18n.EN)


def test_resolve_ui_language():
    assert i18n.resolve_ui_language({"ui": {"language": "bs"}}) == "bs"
    assert i18n.resolve_ui_language({"ui": {"language": "en"}}) == "en"
    assert i18n.resolve_ui_language(
        {"whisper": {"language": "bs"}}) == "bs"  # auto follows dictation
    assert i18n.resolve_ui_language(
        {"whisper": {"language": "hr"}}) == "bs"
    assert i18n.resolve_ui_language({"whisper": {"language": "en"}}) == "en"
    assert i18n.resolve_ui_language({}) == "en"


# ---- injection safety net ---------------------------------------------------

def test_full_delivery_not_suspect():
    assert injection_suspect(sent=10, expected=10) is False


def test_partial_delivery_suspect():
    assert injection_suspect(sent=3, expected=10) is True


def test_zero_delivery_suspect():
    assert injection_suspect(sent=0, expected=10) is True
