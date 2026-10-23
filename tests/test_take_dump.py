"""Opt-in take recorder (DICTATE_DUMP_TAKES): off by default, and when on it
writes a playable WAV plus the text/chunk log for each take."""
import json
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import session as session_mod  # noqa: E402


class _Chunked:
    chunk_log = [(0.0, 2.0, "hello there"), (2.0, 4.0, "")]
    _committed = 4 * 16000


def _dump(tmp_path, monkeypatch, env):
    if env:
        monkeypatch.setenv("DICTATE_DUMP_TAKES", str(tmp_path / "takes"))
    else:
        monkeypatch.delenv("DICTATE_DUMP_TAKES", raising=False)
    cls = next(c for c in vars(session_mod).values()
               if isinstance(c, type) and hasattr(c, "_dump_take"))
    audio = (np.sin(np.linspace(0, 400, 5 * 16000)) * 0.5).astype(np.float32)
    cls._dump_take(None, audio, "hello there", "Hello there.", _Chunked())
    return tmp_path / "takes"


def test_nothing_is_written_unless_enabled(tmp_path, monkeypatch):
    d = _dump(tmp_path, monkeypatch, env=False)
    assert not d.exists()


def test_enabled_writes_wav_and_json(tmp_path, monkeypatch):
    d = _dump(tmp_path, monkeypatch, env=True)
    wavs = list(d.glob("take-*.wav"))
    jsons = list(d.glob("take-*.json"))
    assert len(wavs) == 1 and len(jsons) == 1
    with wave.open(str(wavs[0])) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        assert w.getnframes() == 5 * 16000
    meta = json.loads(jsons[0].read_text())
    assert meta["raw"] == "hello there" and meta["final"] == "Hello there."
    assert meta["chunks"][1] == [2.0, 4.0, ""]
    assert meta["committed_s"] == 4.0
    assert 0.4 < meta["peak"] <= 0.5
