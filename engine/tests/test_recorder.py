# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Meeting recording: sources mixed on one timeline, a stalled one cannot block it."""

import wave

import numpy as np

from continuum.audio.recorder import MAX_LAG_S, MixRecorder

RATE = 16_000


def read(path) -> np.ndarray:
    with wave.open(str(path)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, RATE)
        return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32767


def test_sources_are_mixed_sample_by_sample(tmp_path) -> None:
    recorder = MixRecorder(tmp_path / "m.wav", ("mic", "system"))
    recorder.feed("mic", np.full(1600, 0.25, dtype=np.float32))
    assert recorder.seconds == 0.0  # waits for system audio to cover the same stretch
    recorder.feed("system", np.full(3200, 0.5, dtype=np.float32))
    recorder.close()

    audio = read(tmp_path / "m.wav")
    assert audio.size == 3200
    assert np.allclose(audio[:1600], 0.75, atol=1e-3)
    assert np.allclose(audio[1600:], 0.5, atol=1e-3)
    assert (tmp_path / "m.wav").stat().st_mode & 0o077 == 0


def test_a_stalled_source_is_treated_as_silence(tmp_path) -> None:
    recorder = MixRecorder(tmp_path / "m.wav", ("mic", "system"))
    for _ in range(40):  # 4 s of system audio, nothing from the microphone
        recorder.feed("system", np.full(1600, 0.1, dtype=np.float32))
    assert recorder.seconds >= 4 - MAX_LAG_S
    recorder.close()
    recorder.close()
    assert read(tmp_path / "m.wav").size == 40 * 1600


def test_unknown_sources_and_loud_audio_are_safe(tmp_path) -> None:
    recorder = MixRecorder(tmp_path / "m.wav", ("system",))
    recorder.feed("other", np.ones(1600, dtype=np.float32))
    recorder.feed("system", np.full(1600, 3.0, dtype=np.float32))
    recorder.close()
    assert np.allclose(read(tmp_path / "m.wav"), 1.0, atol=1e-3)
