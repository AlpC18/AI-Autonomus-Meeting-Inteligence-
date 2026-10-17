# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Real PulseAudio check: with two apps playing, only the meeting app is heard.

Run inside Linux with a PulseAudio (or pipewire-pulse) server, while "zoom"
plays 440 Hz and "spotify" plays 1000 Hz; see linux_app_audio_check.sh.
"""

import asyncio
import sys

import numpy as np

from recall.audio.blocks import SAMPLE_RATE
from recall.audio.pulse_apps import (
    BROWSER_BINARIES,
    NATIVE_MEETING_BINARIES,
    pulse_app_blocks,
)


def strength(samples: np.ndarray, hz: float) -> float:
    """Spectrum magnitude within 15 Hz of ``hz``."""
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    freqs = np.fft.rfftfreq(len(samples), 1 / SAMPLE_RATE)
    return float(spectrum[np.abs(freqs - hz) < 15].max())


async def record(seconds: float) -> np.ndarray:
    blocks: list[np.ndarray] = []
    async for block in pulse_app_blocks(NATIVE_MEETING_BINARIES, BROWSER_BINARIES):
        blocks.append(block)
        if sum(len(b) for b in blocks) >= seconds * SAMPLE_RATE:
            break
    return np.concatenate(blocks)


def main() -> int:
    audio = asyncio.run(asyncio.wait_for(record(2.0), timeout=20))
    tail = audio[len(audio) // 2 :]  # skip the start, while the stream is being found
    zoom, spotify = strength(tail, 440), strength(tail, 1000)
    rms = float(np.sqrt(np.mean(tail**2)))
    print(f"heard {len(audio) / SAMPLE_RATE:.1f}s, rms {rms:.3f}, spotify/zoom tone ratio {spotify / zoom:.4f}")
    ok = rms > 0.01 and spotify < zoom * 0.1  # resampling noise alone is ~2%; hearing spotify would be ~180%
    print("PASS: only the meeting app was heard" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
