# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Linux: the meeting app's playback stream is found and recorded on its own."""

import os
import stat
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from recall.audio.follow import Process
from recall.audio.pulse_apps import (
    BROWSER_BINARIES,
    NATIVE_MEETING_BINARIES,
    ParecCapture,
    meeting_stream,
)

STREAMS = [
    {"index": 41, "properties": {"application.name": "Spotify", "application.process.binary": "spotify"}},
    {"index": 57, "properties": {"application.name": "Google Chrome", "application.process.binary": "chrome"}},
    {"index": 63, "properties": {"application.name": "ZOOM VoiceEngine", "application.process.binary": "/opt/zoom/zoom"}},
    {"index": 70, "properties": {}},
]


def test_the_meeting_apps_stream_is_chosen_native_first() -> None:
    assert meeting_stream(STREAMS, NATIVE_MEETING_BINARIES, BROWSER_BINARIES) == Process(63, 0, "zoom")
    assert meeting_stream(STREAMS[:2], NATIVE_MEETING_BINARIES, BROWSER_BINARIES) == Process(57, 0, "chrome")
    assert meeting_stream(STREAMS[:2], NATIVE_MEETING_BINARIES, frozenset()) is None  # tab extension on


@pytest.mark.skipif(sys.platform == "win32", reason="the fake parec is a shell script")
def test_parec_output_becomes_samples(tmp_path: Path) -> None:
    samples = np.array([0, 16384, -16384, 32767], dtype="<i2")
    fake = tmp_path / "parec"
    raw = tmp_path / "samples.raw"
    raw.write_bytes(samples.tobytes())
    fake.write_text(f"#!/bin/sh\ncat '{raw}'\nsleep 5\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    capture = ParecCapture(63, parec=str(fake))
    try:
        got = np.zeros(0, np.float32)
        deadline = time.monotonic() + 3
        while got.size < 4 and time.monotonic() < deadline:
            got = np.concatenate([got, capture.read()])
            time.sleep(0.05)
    finally:
        capture.close()
    assert got.tolist() == [0.0, 0.5, -0.5, 32767 / 32768]
    assert os.path.exists(fake)
