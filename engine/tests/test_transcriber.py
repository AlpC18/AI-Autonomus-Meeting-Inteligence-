# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Speech backends: same output contract, chosen by configuration."""

import os
import shutil
from pathlib import Path

import pytest
from test_pipeline import synthesise

from continuum.audio.chunker import Utterance
from continuum.audio.transcriber import (
    Transcriber,
    load_transcriber,
    mlx_available,
    mlx_repo,
)
from continuum.config import Settings


@pytest.mark.parametrize(
    ("size", "repo"),
    [
        ("base", "mlx-community/whisper-base-mlx"),
        ("small", "mlx-community/whisper-small-mlx"),
        ("large-v3-turbo", "mlx-community/whisper-large-v3-turbo"),
        ("someone/my-whisper", "someone/my-whisper"),
    ],
)
def test_model_sizes_map_to_mlx_repos(size: str, repo: str) -> None:
    assert mlx_repo(size) == repo


def test_backend_setting_is_validated() -> None:
    assert Settings.from_env({}).asr_backend == "auto"
    assert Settings.from_env({"CONTINUUM_ASR_BACKEND": "MLX"}).asr_backend == "mlx"
    with pytest.raises(ValueError, match="CONTINUUM_ASR_BACKEND"):
        Settings.from_env({"CONTINUUM_ASR_BACKEND": "parakeet"})
    with pytest.raises(ValueError):
        load_transcriber("parakeet", "tiny", None)


def _model_dir() -> Path | None:
    value = os.environ.get("CONTINUUM_MODEL_DIR")
    return Path(value) if value else None


@pytest.mark.skipif(shutil.which("say") is None, reason="needs macOS say")
@pytest.mark.parametrize("backend", ["faster-whisper", "mlx"])
def test_backends_return_timed_words_on_the_stream_timeline(backend: str, tmp_path: Path) -> None:
    if backend == "mlx" and not mlx_available():
        pytest.skip("mlx-whisper needs an Apple Silicon Mac with the apple extra")
    samples = synthesise("The budget was revised to thirty five thousand.", tmp_path / "s.wav")
    transcriber = load_transcriber(backend, "tiny", _model_dir())
    assert isinstance(transcriber, Transcriber) == (backend == "faster-whisper")

    segments = transcriber.transcribe(Utterance(100.0, samples), "system")

    assert "budget" in " ".join(segment.text for segment in segments).lower()
    words = [word for segment in segments for word in segment.words]
    assert words and all(100.0 <= word.start <= word.end for word in words)
    assert {segment.speaker for segment in segments} == {"others"}
