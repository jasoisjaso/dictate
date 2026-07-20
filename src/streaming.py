"""Chunked "streaming" transcription for long takes.

Problem: a 60-second dictation transcribed only after key-release means the
user stares at a spinner for seconds. Top commercial tools (Wispr Flow etc.)
feel instant because they transcribe WHILE you talk.

Approach here — deliberately simple and crash-safe:
  * While recording, once enough un-committed audio has accumulated
    (MIN_CHUNK_S), cut it at the quietest moment in the recent past (so we
    never cut mid-word) and transcribe that chunk in this worker thread.
  * Committed chunk texts accumulate in order; each chunk gets the previous
    chunk's tail as context so names/terms stay consistent.
  * On stop, only the short remaining tail needs transcribing — the final
    result appears near-instantly even for multi-minute takes.

Short takes (under MIN_CHUNK_S) never trigger a commit, so the normal
short-dictation path is completely unchanged.

Hardware gating lives in device.streaming_ok(): GPU always qualifies; CPU
only with a small model and enough cores. ui.py checks it before creating a
ChunkedTake at all.
"""
from __future__ import annotations

import logging
import threading

import numpy as np

log = logging.getLogger("dictate.streaming")

SAMPLE_RATE = 16000

MIN_CHUNK_S = 14.0    # commit only once this much uncommitted audio exists
CUT_SEARCH_S = 5.0    # search the last N s (before the keep zone) for a cut
TAIL_KEEP_S = 1.0     # never cut into the most recent second (mid-word risk)
CUT_WIN_S = 0.30      # RMS window used to find the quietest moment


def find_cut_sample(uncommitted: np.ndarray, sr: int = SAMPLE_RATE,
                    search_s: float = CUT_SEARCH_S,
                    keep_s: float = TAIL_KEEP_S,
                    win_s: float = CUT_WIN_S) -> int:
    """Index into `uncommitted` where it's safest to cut a chunk.

    Scans the region [end - search_s - keep_s, end - keep_s] for the
    quietest `win_s` window (lowest RMS ≈ a pause between words/sentences)
    and returns the centre of that window. Pure function — unit-testable.
    """
    n = uncommitted.size
    keep = int(keep_s * sr)
    search = int(search_s * sr)
    win = max(1, int(win_s * sr))
    end = n - keep
    start = max(0, end - search)
    if end - start < win * 2:
        # not enough room to search; cut at the start of the keep zone
        return max(1, end)
    region = uncommitted[start:end]
    # windowed RMS via cumulative sum of squares (fast, no python loop)
    sq = np.square(region.astype(np.float64))
    csum = np.cumsum(sq)
    window_energy = csum[win - 1:] - np.concatenate(([0.0], csum[:-win]))
    best = int(np.argmin(window_energy))
    return start + best + win // 2


class ChunkedTake:
    """Background chunk-committer for one recording take.

    Life cycle: create at recording start, `start()` the worker, then either
    `finalize(full_audio)` after stop (returns the full raw transcript) or
    `cancel()` on abort. One instance per take — never reused.
    """

    def __init__(self, engine, recorder, on_commit=None,
                 samplerate: int = SAMPLE_RATE):
        self.engine = engine
        self.recorder = recorder
        self.on_commit = on_commit      # callback(committed_text_so_far)
        self.sr = samplerate
        self._texts: list[str] = []
        self._committed = 0             # samples committed so far
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._stop.set()

    # ---- worker ----------------------------------------------------------

    def _run(self):
        min_chunk = int(MIN_CHUNK_S * self.sr)
        while not self._stop.wait(1.0):
            try:
                buf = self.recorder.snapshot()
                uncommitted = buf[self._committed:]
                if uncommitted.size < min_chunk:
                    continue
                cut = find_cut_sample(uncommitted, self.sr)
                chunk = uncommitted[:cut]
                if chunk.size < self.sr:  # sanity: never commit <1s
                    continue
                prev = self._texts[-1] if self._texts else None
                text = self.engine.transcribe_audio_buffer(chunk,
                                                           prev_text=prev)
                # commit the position even if the text came back empty —
                # re-transcribing the same silent audio forever helps no one
                self._committed += cut
                if text:
                    self._texts.append(text)
                    log.info("committed chunk #%d (%.1fs, %d chars)",
                             len(self._texts), chunk.size / self.sr,
                             len(text))
                    if self.on_commit:
                        try:
                            self.on_commit(" ".join(self._texts))
                        except Exception:
                            pass
            except Exception as ex:
                # a failed commit must never kill the take: the finalize()
                # path will simply transcribe more tail audio
                log.warning("chunk commit failed (non-fatal): %s", ex)

    # ---- completion ------------------------------------------------------

    def finalize(self, full_audio: np.ndarray) -> str:
        """Stop committing, transcribe the remaining tail, return everything."""
        self._stop.set()
        if self._thread is not None:
            # a commit may be in flight holding the engine lock; wait for it
            self._thread.join(timeout=60.0)
            if self._thread.is_alive():
                log.warning("chunk worker still busy after 60s — "
                            "falling back to full re-transcription")
                return self.engine.transcribe_audio_buffer(full_audio)
        tail = full_audio[self._committed:]
        prev = self._texts[-1] if self._texts else None
        tail_text = ""
        if tail.size >= 1600:
            tail_text = self.engine.transcribe_audio_buffer(tail,
                                                            prev_text=prev)
        parts = [t for t in self._texts + [tail_text] if t]
        return " ".join(parts).strip()
