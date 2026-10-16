# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Captures only the meeting app's audio on Linux (PulseAudio or PipeWire).

Each app plays through its own stream ("sink input"). The meeting app's
stream is found with ``pactl`` and recorded with ``parec --monitor-stream``,
which only listens: the user's audio routing is not changed. PipeWire
offers the same through ``pipewire-pulse``. When the tools are missing the
caller falls back to all system audio.
"""

import asyncio
import json
import os
import shutil
import subprocess
import threading
from collections.abc import AsyncIterator, Iterable
from typing import Any

import numpy as np

from continuum.audio.blocks import SAMPLE_RATE, BlockQueue
from continuum.audio.follow import Process, follow_app

NATIVE_MEETING_BINARIES = frozenset(
    {
        "zoom", "teams", "teams-for-linux", "slack", "discord", "skypeforlinux", "webex",
        "telegram-desktop", "signal-desktop", "element-desktop", "whatsapp-for-linux", "jitsi-meet",
    }
)
"""Process names of meeting apps other than browsers."""

BROWSER_BINARIES = frozenset(
    {"chrome", "google-chrome", "chromium", "chromium-browser", "firefox", "brave", "msedge", "opera", "vivaldi"}
)

_READ_BYTES = 65536


def meeting_stream(sink_inputs: Iterable[dict[str, Any]], native: frozenset[str], browsers: frozenset[str]) -> Process | None:
    """The playback stream of the meeting app to hear (``pid`` is the sink input's index); native apps first."""
    candidates = []
    for stream in sink_inputs:
        properties = stream.get("properties") or {}
        binary = os.path.basename(str(properties.get("application.process.binary") or "")).lower()
        index = stream.get("index")
        if binary and isinstance(index, int):
            candidates.append(Process(index, 0, binary))
    for group in (native, browsers):
        found = sorted((stream for stream in candidates if stream.name in group), key=lambda stream: stream.pid)
        if found:
            return found[0]
    return None


def sink_inputs() -> list[dict[str, Any]]:
    """Every playback stream, from ``pactl -f json list sink-inputs``.

    Raises:
        RuntimeError: if ``pactl`` is missing, fails, or is too old for JSON output.
    """
    pactl = shutil.which("pactl")
    if pactl is None:
        raise RuntimeError("pactl is not installed (pulseaudio-utils)")
    result = subprocess.run(
        [pactl, "-f", "json", "list", "sink-inputs"], capture_output=True, text=True, timeout=5, check=False
    )
    try:
        parsed = json.loads(result.stdout) if result.returncode == 0 else None
    except json.JSONDecodeError:
        parsed = None
    streams = parsed if isinstance(parsed, list) else None
    if streams is None:
        raise RuntimeError("pactl could not list playback streams as JSON (PulseAudio 16 or PipeWire needed)")
    return streams


class ParecCapture:
    """One playback stream's audio, recorded by ``parec`` at 16 kHz mono."""

    def __init__(self, index: int, parec: str = "parec") -> None:
        self._process = subprocess.Popen(
            [parec, f"--monitor-stream={index}", "--format=s16le", f"--rate={SAMPLE_RATE}", "--channels=1",
             "--raw", "--latency-msec=50"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        assert self._process.stdout is not None
        self._out = self._process.stdout.fileno()
        os.set_blocking(self._out, False)
        self._partial = b""

    def read(self) -> np.ndarray:
        """Every sample recorded since the last call, as float32 in [-1, 1]."""
        data = self._partial
        while True:
            try:
                chunk = os.read(self._out, _READ_BYTES)
            except BlockingIOError:
                break
            if not chunk:
                break
            data += chunk
        whole = len(data) - len(data) % 2
        self._partial = data[whole:]
        return np.frombuffer(data[:whole], dtype="<i2").astype(np.float32) / 32768.0

    def close(self) -> None:
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()


async def pulse_app_blocks(native: frozenset[str], browsers: frozenset[str]) -> AsyncIterator[np.ndarray]:
    """Yield 100 ms mono float32 blocks of the meeting app's audio. Runs until the consumer stops.

    Raises:
        RuntimeError: if ``pactl`` or ``parec`` is unavailable (the caller then hears all system audio).
    """
    sink_inputs()  # fail now, so the caller can fall back, rather than in the thread
    if shutil.which("parec") is None:
        raise RuntimeError("parec is not installed (pulseaudio-utils)")
    queue = BlockQueue("Meeting app")
    stopped = threading.Event()

    def choose() -> Process | None:
        return meeting_stream(sink_inputs(), native, browsers)

    thread = threading.Thread(target=follow_app, args=(queue, stopped, choose, ParecCapture), name="pulse-app", daemon=True)
    thread.start()
    try:
        async for block in queue:
            yield block
    finally:
        stopped.set()
        await asyncio.to_thread(thread.join, 2)
