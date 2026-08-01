"""Parakeet second engine: routing table, transcriber interface (stubbed
sherpa-onnx — CI never downloads 640 MB), fail-open factory, cache checks."""
import os
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import device
import engine as engine_mod
import engine_parakeet
import first_run
from device import Tier, choose_engine, streaming_ok
from engine_parakeet import PARAKEET_LANGS, ParakeetTranscriber

CPU = Tier("cpu", "int8", "small")
GPU = Tier("cuda", "float16", "large-v3-turbo")


# ---- choose_engine routing table -------------------------------------------
# Every rule from docs/parakeet-engine.md §3.3.

@pytest.mark.parametrize("cfg,tier,lang,want", [
    # auto: CPU + supported language -> parakeet
    ("auto", CPU, "en", "parakeet"),
    ("auto", CPU, "hr", "parakeet"),
    ("auto", CPU, "de", "parakeet"),
    # auto: unsupported languages stay on whisper
    ("auto", CPU, "bs", "whisper"),
    ("auto", CPU, "sr", "whisper"),
    ("auto", CPU, "ja", "whisper"),
    # auto: synthetic modes all depend on bs recognition -> whisper
    ("auto", CPU, "auto", "whisper"),
    ("auto", CPU, "multi", "whisper"),
    ("auto", CPU, "bs2en", "whisper"),
    ("auto", CPU, "en2bs", "whisper"),
    # auto: CUDA keeps whisper (prompts + dictionary biasing win there)
    ("auto", GPU, "en", "whisper"),
    ("auto", GPU, "hr", "whisper"),
    # explicit whisper always wins
    ("whisper", CPU, "en", "whisper"),
    ("whisper", GPU, "en", "whisper"),
    # explicit parakeet wins for supported languages, even on GPU
    ("parakeet", CPU, "en", "parakeet"),
    ("parakeet", GPU, "en", "parakeet"),
    ("parakeet", GPU, "fr", "parakeet"),
    # explicit parakeet + unsupported language forces whisper (honest
    # fallback, never a silent wrong-language result)
    ("parakeet", CPU, "bs", "whisper"),
    ("parakeet", GPU, "sr", "whisper"),
    ("parakeet", CPU, "multi", "whisper"),
    ("parakeet", CPU, "bs2en", "whisper"),
    # unknown config values behave like auto
    ("bogus", CPU, "en", "parakeet"),
    ("", GPU, "en", "whisper"),
])
def test_choose_engine_table(cfg, tier, lang, want):
    assert choose_engine(cfg, tier, lang) == want


def test_parakeet_langs_sanity():
    # 25 languages per the model card; the ones the routing rules hinge on
    assert len(PARAKEET_LANGS) == 25
    assert "en" in PARAKEET_LANGS and "hr" in PARAKEET_LANGS
    assert "bs" not in PARAKEET_LANGS and "sr" not in PARAKEET_LANGS


# ---- streaming gate is engine-aware -----------------------------------------

def test_streaming_ok_parakeet_always():
    slow_cpu = Tier("cpu", "int8", "large-v3-turbo")
    assert streaming_ok(slow_cpu, "parakeet")
    assert streaming_ok(GPU, "parakeet")


def test_streaming_ok_whisper_rules_unchanged(monkeypatch):
    assert streaming_ok(GPU)                       # default engine = whisper
    monkeypatch.setattr(device, "_cpu_cores", lambda: 4)
    assert not streaming_ok(CPU, "whisper")        # 4 cores: below the gate


# ---- stubbed sherpa-onnx ----------------------------------------------------

class _FakeStream:
    def __init__(self, text):
        self.result = types.SimpleNamespace(text=text)

    def accept_waveform(self, sr, audio):
        assert sr == 16000
        self.n_samples = len(audio)


class _FakeRecognizer:
    last_kwargs = None
    reply = " hello world "

    def create_stream(self):
        return _FakeStream(self.reply)

    def decode_stream(self, stream):
        pass

    @classmethod
    def from_transducer(cls, **kw):
        cls.last_kwargs = kw
        return cls()


@pytest.fixture
def stub_sherpa(monkeypatch):
    mod = types.ModuleType("sherpa_onnx")
    mod.OfflineRecognizer = _FakeRecognizer
    monkeypatch.setitem(sys.modules, "sherpa_onnx", mod)
    return mod


@pytest.fixture
def model_dir(tmp_path):
    d = tmp_path / "parakeet-model"
    d.mkdir()
    for name in ("encoder.int8.onnx", "decoder.int8.onnx",
                 "joiner.int8.onnx", "tokens.txt"):
        (d / name).write_bytes(b"x")
    return d


def _cfg(model_dir=None, **extra):
    cfg = {"whisper": {"language": "en"}}
    if model_dir is not None:
        cfg["parakeet"] = {"model_dir": str(model_dir)}
    cfg.update(extra)
    return cfg


# ---- ParakeetTranscriber interface ------------------------------------------

def test_engine_name_and_no_hotwords():
    t = ParakeetTranscriber(_cfg())
    assert t.engine_name == "parakeet"
    assert t.hotwords is None and t.initial_prompt is None
    assert t.model_size == "parakeet-tdt-0.6b-v3"


def test_auto_punctuation_always_forced_off():
    # even an explicit true (set for a small Whisper model) must not run our
    # heuristic on top of Parakeet's native punctuation
    t = ParakeetTranscriber(_cfg(post_processing={"auto_punctuation": True}))
    assert t.auto_punctuation is False


def test_synthetic_language_modes_resolve_like_whisper():
    t = ParakeetTranscriber({"whisper": {"language": "multi"}})
    assert t.language is None
    assert t.translate_to_en is False and t.translate_to_bs is False


def test_post_process_shared_pipeline():
    # lexicon + fillers + dictionary come from TextPipeline — the exact same
    # code Whisper runs, not a copy
    t = ParakeetTranscriber(_cfg(dictionary={"woolies": "Woolworths"}))
    out = t.post_process("um we shop at woolies comma right")
    assert "um" not in out.lower().split()
    assert "Woolworths" in out
    assert "," in out
    assert "comma" not in out.lower()


def test_transcribe_uses_sherpa_and_ignores_prev_text(stub_sherpa, model_dir):
    t = ParakeetTranscriber(_cfg(model_dir=model_dir))
    audio = np.zeros(16000, dtype=np.float32)
    assert t.transcribe_audio_buffer(audio, prev_text="ignored") == "hello world"
    kw = _FakeRecognizer.last_kwargs
    assert kw["model_type"] == "nemo_transducer"
    assert kw["encoder"].endswith("encoder.int8.onnx")
    assert t.active_device == "cpu"


def test_transcribe_tiny_buffer_short_circuits(stub_sherpa, model_dir):
    t = ParakeetTranscriber(_cfg(model_dir=model_dir))
    assert t.transcribe_audio_buffer(np.zeros(100, dtype=np.float32)) == ""


def test_preview_ok_contract(monkeypatch):
    # engine-owned gate: Parakeet affordable even on CPU, Whisper CUDA-only
    assert ParakeetTranscriber(_cfg()).preview_ok is True
    monkeypatch.setattr(device, "detect", lambda: CPU)
    cfg = {"whisper": {"model_size": "small", "device": "cpu",
                       "compute_type": "int8", "language": "en"},
           "engine": {"engine": "whisper"}}
    assert engine_mod.create_engine(cfg).preview_ok is False


def test_preview_decodes_when_loaded(stub_sherpa, model_dir):
    t = ParakeetTranscriber(_cfg(model_dir=model_dir))
    t.load()
    out = t.try_preview_transcribe(np.zeros(32000, dtype=np.float32))
    assert out == "hello world"


def test_preview_none_before_load_and_when_busy(stub_sherpa, model_dir):
    t = ParakeetTranscriber(_cfg(model_dir=model_dir))
    audio = np.zeros(32000, dtype=np.float32)
    assert t.try_preview_transcribe(audio) is None  # not loaded yet
    t.load()
    with t._lock:  # a chunk commit / final pass is holding the engine
        assert t.try_preview_transcribe(audio) is None


# ---- quiet-mic normalisation -------------------------------------------------

def test_normalize_boosts_quiet_audio():
    quiet = np.full(1600, 0.05, dtype=np.float32)
    out = engine_parakeet._normalize(quiet)
    assert np.isclose(np.max(np.abs(out)), 0.9, atol=0.01)


def test_normalize_leaves_healthy_audio_alone():
    loud = np.full(1600, 0.95, dtype=np.float32)
    assert engine_parakeet._normalize(loud) is loud


def test_normalize_never_amplifies_dead_silence():
    silence = np.full(1600, 1e-5, dtype=np.float32)
    assert engine_parakeet._normalize(silence) is silence


def test_normalize_gain_is_capped():
    faint = np.full(1600, 2e-4, dtype=np.float32)
    out = engine_parakeet._normalize(faint)
    assert np.max(np.abs(out)) <= 2e-4 * engine_parakeet._GAIN_CAP + 1e-9


def test_load_raises_cleanly_when_model_missing(stub_sherpa, tmp_path):
    t = ParakeetTranscriber(_cfg(model_dir=tmp_path / "empty"))
    with pytest.raises(RuntimeError, match="missing"):
        t.load()


# ---- model file discovery ----------------------------------------------------

def test_resolve_model_files_prefers_int8(model_dir):
    (model_dir / "encoder.onnx").write_bytes(b"x")  # fp32 next to int8
    files = engine_parakeet.resolve_model_files(str(model_dir))
    assert files is not None
    assert files["encoder"].endswith("encoder.int8.onnx")


def test_resolve_model_files_missing_piece(tmp_path):
    d = tmp_path / "half"
    d.mkdir()
    (d / "encoder.int8.onnx").write_bytes(b"x")
    assert engine_parakeet.resolve_model_files(str(d)) is None


def test_parakeet_is_cached(tmp_path, model_dir):
    assert first_run.parakeet_is_cached(str(tmp_path), str(model_dir))
    assert not first_run.parakeet_is_cached(str(tmp_path))  # default dir empty


# ---- create_engine factory ----------------------------------------------------

def test_factory_picks_parakeet_when_available(stub_sherpa, monkeypatch):
    monkeypatch.setattr(device, "detect", lambda: CPU)
    eng = engine_mod.create_engine(_cfg(engine={"engine": "parakeet"}))
    assert eng.engine_name == "parakeet"
    assert eng.engine_note is None


def test_factory_falls_back_without_sherpa(monkeypatch):
    monkeypatch.setattr(device, "detect", lambda: CPU)
    # sys.modules[name] = None makes `import sherpa_onnx` raise ImportError
    monkeypatch.setitem(sys.modules, "sherpa_onnx", None)
    eng = engine_mod.create_engine(_cfg(engine={"engine": "parakeet"}))
    assert eng.engine_name == "whisper"
    assert "Parakeet" in (eng.engine_note or "")


def test_factory_unsupported_language_notes_whisper(monkeypatch):
    monkeypatch.setattr(device, "detect", lambda: CPU)
    cfg = {"whisper": {"language": "bs"}, "engine": {"engine": "parakeet"}}
    eng = engine_mod.create_engine(cfg)
    assert eng.engine_name == "whisper"
    assert "bs" in (eng.engine_note or "")


def test_factory_explicit_whisper_never_probes_hardware(monkeypatch):
    def boom():
        raise AssertionError("detect() must not run for explicit whisper")
    monkeypatch.setattr(device, "detect", boom)
    cfg = {"whisper": {"model_size": "small", "device": "cpu",
                       "compute_type": "int8", "language": "en"},
           "engine": {"engine": "whisper"}}
    eng = engine_mod.create_engine(cfg)
    assert eng.engine_name == "whisper"
    assert eng.engine_note is None
