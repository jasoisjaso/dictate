"""Asynchronous microphone capture with hardware-disconnect recovery."""

import logging
import threading
import time

import numpy as np
import sounddevice as sd

log = logging.getLogger("dictate.audio")

SAMPLE_RATE = 16000
BLOCK_SIZE = 512  # 32 ms at 16 kHz


class AudioRecorder:
    """Non-blocking mic capture. Callback thread appends raw float32 blocks to
    a lock-guarded list; the GUI/worker threads read via stop_recording() or
    peek_tail(). If the input device vanishes (USB headset unplugged), the
    stream is rebuilt automatically on the next start."""

    def __init__(self, samplerate: int = SAMPLE_RATE, blocksize: int = BLOCK_SIZE):
        self.samplerate = samplerate
        self.blocksize = blocksize
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._active = False
        self._stream = None

    @property
    def is_recording(self) -> bool:
        return self._active

    @property
    def duration(self) -> float:
        with self._lock:
            n = sum(len(c) for c in self._chunks)
        return n / self.samplerate

    def _callback(self, indata, frames, time_info, status):
        if status:
            log.debug("audio status: %s", status)
        if self._active:
            with self._lock:
                self._chunks.append(indata[:, 0].copy())

    def _ensure_stream(self, retries: int = 3, retry_delay: float = 1.0):
        if self._stream is not None:
            try:
                if self._stream.active:
                    return
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        last_err = None
        for attempt in range(retries):
            try:
                self._stream = sd.InputStream(
                    samplerate=self.samplerate,
                    channels=1,
                    dtype="float32",
                    blocksize=self.blocksize,
                    callback=self._callback,
                )
                self._stream.start()
                log.info("input stream started (device=%s)", sd.default.device)
                return
            except Exception as ex:
                last_err = ex
                log.warning("input stream attempt %d failed: %s", attempt + 1, ex)
                # force sounddevice to re-scan hardware after a disconnect
                try:
                    sd._terminate()
                    sd._initialize()
                except Exception:
                    pass
                time.sleep(retry_delay)
        raise RuntimeError(f"no usable microphone: {last_err}")

    def start_recording(self):
        with self._lock:
            self._chunks = []
        self._ensure_stream()
        self._active = True

    def stop_recording(self) -> np.ndarray:
        """Stop capturing and return the whole take as 1-D float32 @16 kHz."""
        self._active = False
        with self._lock:
            chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)

    def abort(self):
        self._active = False
        with self._lock:
            self._chunks = []

    def current_level(self, window: float = 0.05) -> float:
        """RMS loudness of the most recent `window` seconds, 0.0..~1.0.
        Drives the live waveform overlay. Returns 0 when not recording."""
        if not self._active:
            return 0.0
        tail = self.peek_tail(window)
        if tail.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(tail))))

    def peek_tail(self, seconds: float) -> np.ndarray:
        """Copy of the most recent `seconds` of audio (for live VAD checks)."""
        want = int(seconds * self.samplerate)
        with self._lock:
            got, take = 0, []
            for c in reversed(self._chunks):
                take.append(c)
                got += len(c)
                if got >= want:
                    break
        if not take:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(list(reversed(take)))[-want:]

    def close(self):
        self._active = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
