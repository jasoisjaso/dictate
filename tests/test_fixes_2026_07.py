"""Regression tests for the July 2026 crash/long-sentence fix batch.

Covers:
- Bosnian real words ("pa", "ma", "e", "znaci", ...) are no longer stripped
  as fillers (they mangled long Bosnian dictations).
- default_fillers() only adds BS hesitations for bs/hr/sr.
- Dictionary terms now go through `hotwords`, not initial_prompt (the model
  used to imitate the "Terms: ..." prompt into transcripts).
- try_preview_transcribe never blocks when the engine lock is held.
"""
import os
import sys
import threading

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cleanup
from engine import WhisperTranscriber


# ---- filler-list language safety -------------------------------------------

def test_bosnian_real_words_survive_default_fillers():
    # These are real Bosnian words that were previously stripped as "fillers"
    rx = cleanup._build_filler_re(cleanup.default_fillers("bs"))
    text = "pa dobro e sad znaci dakle ono ma vale ajde idemo"
    assert cleanup.strip_fillers(text, rx) == text


def test_english_fillers_still_stripped_for_bosnian():
    rx = cleanup._build_filler_re(cleanup.default_fillers("bs"))
    assert cleanup.strip_fillers("um pa dobro uh idemo", rx) == "pa dobro idemo"


def test_bs_hesitations_stripped_for_bosnian():
    rx = cleanup._build_filler_re(cleanup.default_fillers("bs"))
    assert cleanup.strip_fillers("ovaj idemo hmm sada", rx) == "idemo sada"


def test_english_list_has_no_bs_entries():
    fillers = cleanup.default_fillers("en")
    assert "ovaj" not in fillers
    assert "pa" not in fillers
    assert "um" in fillers


def test_default_fillers_none_language():
    assert cleanup.default_fillers(None) == list(cleanup.FILLERS)


# ---- hotwords replaces the initial_prompt hijack ---------------------------

def test_dictionary_populates_hotwords_not_prompt():
    t = WhisperTranscriber({"dictionary": {"woolies": "Woolworths",
                                           "sap": "SAP Ariba"}})
    assert t.initial_prompt is None
    assert "Woolworths" in t.hotwords
    assert "SAP Ariba" in t.hotwords


def test_user_initial_prompt_untouched_by_dictionary():
    t = WhisperTranscriber({
        "whisper": {"initial_prompt": "Warehouse dictation."},
        "dictionary": {"woolies": "Woolworths"},
    })
    assert t.initial_prompt == "Warehouse dictation."
    assert t.hotwords is not None


def test_no_dictionary_means_no_hotwords():
    t = WhisperTranscriber({})
    assert t.hotwords is None


# ---- preview must not block on a busy engine -------------------------------

def test_preview_returns_none_when_engine_busy():
    t = WhisperTranscriber({})
    t._model = object()  # pretend a model is loaded
    audio = np.zeros(16000, dtype=np.float32)
    with t._lock:  # simulate a running final transcription
        done = []

        def probe():
            done.append(t.try_preview_transcribe(audio))

        th = threading.Thread(target=probe)
        th.start()
        th.join(timeout=2.0)
        assert not th.is_alive(), "preview blocked on a busy engine"
    assert done == [None]


def test_preview_none_without_model():
    t = WhisperTranscriber({})
    assert t.try_preview_transcribe(np.zeros(16000, dtype=np.float32)) is None


def test_preview_none_on_tiny_buffer():
    t = WhisperTranscriber({})
    t._model = object()
    assert t.try_preview_transcribe(np.zeros(100, dtype=np.float32)) is None
