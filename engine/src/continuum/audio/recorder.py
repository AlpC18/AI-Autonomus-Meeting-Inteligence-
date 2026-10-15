# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Records a meeting's audio: every source mixed into one WAV file.

Recording is off unless the user turns it on. The file sits next to the
meeting's notes so the viewer can play the meeting back; it holds exactly
what was heard, so redaction does not apply to it.
"""

import wave
from pathlib import Path

import numpy as np

from continuum.audio.blocks import SAMPLE_RATE

MAX_LAG_S = 2.0
"""A source this far behind the others is taken to be silent (stalled or stopped)."""


class MixRecorder:
    """Mixes the meeting's sources into one 16 kHz mono 16-bit WAV as audio arrives.

    Sources deliver blocks at their own pace, so each is buffered and only the
    stretch every source has covered is mixed and written. A source more than
    :data:`MAX_LAG_S` behind is padded with silence, so a stalled microphone
    neither blocks the recording nor makes memory grow. Not thread-safe: feed
    it from one thread (the event loop).
    """

    def __init__(self, path: Path, sources: tuple[str, ...]) -> None:
        """Create (or replace) the WAV file at ``path``, readable by this user only.

        Raises:
            OSError: if the file cannot be created.
        """
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = path
        self._wav = wave.open(str(path), "wb")  # noqa: SIM115 - closed in close()
        path.chmod(0o600)
        self._wav.setnchannels(1)
        self._wav.setsampwidth(2)
        self._wav.setframerate(SAMPLE_RATE)
        self._buffers = {source: np.zeros(0, dtype=np.float32) for source in sources}
        self._max_lag = int(MAX_LAG_S * SAMPLE_RATE)

    def feed(self, source: str, block: np.ndarray) -> None:
        """Add ``block`` (mono float32 at 16 kHz) captured from ``source``."""
        if source not in self._buffers or self._wav is None:
            return
        self._buffers[source] = np.concatenate([self._buffers[source], block.astype(np.float32)])
        lengths = [buffer.size for buffer in self._buffers.values()]
        ready = max(min(lengths), max(lengths) - self._max_lag)
        if ready > 0:
            self._write(ready)

    def _write(self, count: int) -> None:
        mixed = np.zeros(count, dtype=np.float32)
        for source, buffer in self._buffers.items():
            used = buffer[:count]
            mixed[: used.size] += used
            self._buffers[source] = buffer[count:]
        pcm = (np.clip(mixed, -1.0, 1.0) * 32767).astype("<i2")
        assert self._wav is not None
        self._wav.writeframes(pcm.tobytes())

    @property
    def seconds(self) -> float:
        """How much audio has been written so far."""
        return self._wav.getnframes() / SAMPLE_RATE if self._wav is not None else 0.0

    def close(self) -> None:
        """Write whatever is buffered and finish the file. Safe to call twice."""
        if self._wav is None:
            return
        remaining = max(buffer.size for buffer in self._buffers.values()) if self._buffers else 0
        if remaining:
            self._write(remaining)
        self._wav.close()
        self._wav = None
