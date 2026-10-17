# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Real WASAPI check: with two apps playing, only the meeting app is heard (Windows 10 2004+).

Copies of the Python interpreter named zoom.exe and spotify.exe play 440 Hz
and 1000 Hz at the same time; process loopback must record only zoom's.

    uv run python scripts/windows_app_audio_check.py
"""

import asyncio
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

from recall.audio.blocks import SAMPLE_RATE
from recall.audio.process_loopback import process_loopback_blocks
from recall.audio.windows_apps import BROWSER_EXES, NATIVE_MEETING_EXES

PLAYER = "import sys, time, winsound; winsound.PlaySound(sys.argv[1], winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP); time.sleep(60)"


def tone(path: Path, hz: float, volume: float) -> None:
    rate = 48000
    t = np.arange(rate * 2) / rate
    samples = (np.sin(2 * np.pi * hz * t) * volume * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples.tobytes())


def app(name: str) -> Path:
    """The base interpreter under another name, next to its DLLs and standard library."""
    base = Path(getattr(sys, "_base_executable", sys.executable))
    copy = base.with_name(name)
    shutil.copy2(base, copy)
    return copy


def strength(samples: np.ndarray, hz: float) -> float:
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    freqs = np.fft.rfftfreq(len(samples), 1 / SAMPLE_RATE)
    return float(spectrum[np.abs(freqs - hz) < 15].max())


async def record(seconds: float) -> np.ndarray:
    blocks: list[np.ndarray] = []
    async for block in process_loopback_blocks(NATIVE_MEETING_EXES, BROWSER_EXES):
        blocks.append(block)
        if sum(len(b) for b in blocks) >= seconds * SAMPLE_RATE:
            break
    return np.concatenate(blocks)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        tone(folder / "440.wav", 440, 0.5)
        tone(folder / "1000.wav", 1000, 0.9)
        players = [
            subprocess.Popen([str(app("zoom.exe")), "-c", PLAYER, str(folder / "440.wav")]),
            subprocess.Popen([str(app("spotify.exe")), "-c", PLAYER, str(folder / "1000.wav")]),
        ]
        try:
            audio = asyncio.run(asyncio.wait_for(record(3.0), timeout=30))
        finally:
            for player in players:
                player.kill()
    tail = audio[len(audio) // 2 :]  # skip the start, while the process is being found
    zoom, spotify = strength(tail, 440), strength(tail, 1000)
    rms = float(np.sqrt(np.mean(tail**2)))
    print(f"heard {len(audio) / SAMPLE_RATE:.1f}s, rms {rms:.3f}, spotify/zoom tone ratio {spotify / max(zoom, 1e-9):.4f}")
    ok = rms > 0.01 and spotify < zoom * 0.1  # resampling noise alone is ~2%; hearing spotify would be ~180%
    print("PASS: only the meeting app was heard" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
