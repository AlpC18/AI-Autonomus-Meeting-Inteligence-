# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""End to end: spoken audio fed to the engine comes out as published words.

Uses the real Whisper "tiny" model (downloaded once) and the macOS `say`
command to synthesise speech, so it is skipped where `say` is unavailable.
"""

import os
import shutil
import subprocess
import wave
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from continuum.audio.transcriber import Transcriber
from continuum.factcheck.checker import FactCheckAlert
from continuum.pipeline import Engine
from continuum.transcript import Segment

pytestmark = pytest.mark.skipif(shutil.which("say") is None, reason="needs macOS say")


def synthesise(text: str, path: Path) -> np.ndarray:
    subprocess.run(
        ["say", "-o", str(path), "--data-format=LEI16@16000", text], check=True
    )
    with wave.open(str(path)) as wav:
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


async def as_blocks(samples: np.ndarray) -> AsyncIterator[np.ndarray]:
    padded = np.concatenate([samples, np.zeros(16_000, dtype=np.float32)])
    for start in range(0, padded.size, 1600):
        yield padded[start : start + 1600]


async def test_spoken_audio_is_published_as_timed_words(tmp_path: Path) -> None:
    samples = synthesise("The budget was revised to thirty five thousand.", tmp_path / "s.wav")
    model_dir = os.environ.get("CONTINUUM_MODEL_DIR")
    published: list[Segment] = []
    remembered: list[Segment] = []
    engine = Engine(
        Transcriber("tiny", Path(model_dir) if model_dir else None),
        published.append,
        remember=lambda segment, _disputed: remembered.append(segment),
    )

    await engine.run_source("system", as_blocks(samples))

    text = " ".join(segment.text for segment in published).lower()
    assert "budget" in text
    words = [word for segment in published for word in segment.words]
    assert words and all(0.0 <= word.start <= word.end for word in words)
    assert {segment.speaker for segment in published} == {"others"}
    assert remembered == published


async def test_memory_failure_does_not_stop_the_live_transcript(tmp_path: Path) -> None:
    samples = synthesise("The budget was revised.", tmp_path / "s.wav")
    model_dir = os.environ.get("CONTINUUM_MODEL_DIR")
    published: list[Segment] = []

    def failing_memory(_segment: Segment, _disputed: bool) -> None:
        raise OSError("disk full")

    engine = Engine(
        Transcriber("tiny", Path(model_dir) if model_dir else None),
        published.append,
        remember=failing_memory,
    )

    await engine.run_source("system", as_blocks(samples))

    assert published


async def test_statement_is_checked_before_it_is_stored(tmp_path: Path) -> None:
    samples = synthesise("The budget was revised.", tmp_path / "s.wav")
    model_dir = os.environ.get("CONTINUUM_MODEL_DIR")
    events: list[str] = []
    alerts: list[FactCheckAlert] = []
    alert = FactCheckAlert(
        "said", "others", ("$50k",), ("$35,000",), "record", "me", datetime.now(UTC), "m1"
    )

    def check(_segment: Segment) -> FactCheckAlert:
        events.append("check")
        return alert

    engine = Engine(
        Transcriber("tiny", Path(model_dir) if model_dir else None),
        lambda _segment: events.append("publish"),
        remember=lambda _segment, disputed: events.append(f"remember disputed={disputed}"),
        check=check,
        publish_alert=alerts.append,
    )

    await engine.run_source("system", as_blocks(samples))

    assert events[:3] == ["publish", "check", "remember disputed=True"]
    assert alerts and alerts[0] is alert
