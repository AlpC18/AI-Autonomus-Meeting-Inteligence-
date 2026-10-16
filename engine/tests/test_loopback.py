# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""System audio on Windows/Linux: speaker loopback as 16 kHz mono blocks."""

import numpy as np
import pytest

from continuum.audio.loopback import loopback_blocks


class FakeRecorder:
    def __init__(self, fail_after: int | None) -> None:
        self.calls, self.fail_after = 0, fail_after

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def record(self, numframes: int) -> np.ndarray:
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise OSError("device unplugged")
        return np.tile(np.array([[0.2, 0.4]], dtype=np.float32), (numframes, 1))


class FakeSoundcard:
    def __init__(self, speaker_name: str | None = "Speakers", fail_after: int | None = None) -> None:
        self.speaker = None if speaker_name is None else type("Speaker", (), {"name": speaker_name})()
        self.recorder = FakeRecorder(fail_after)
        self.asked: dict = {}

    def default_speaker(self):
        return self.speaker

    def get_microphone(self, id: str, include_loopback: bool):
        self.asked = {"id": id, "include_loopback": include_loopback}
        if id != "Speakers":
            raise IndexError(id)
        outer = self

        class Device:
            def recorder(self, samplerate: int, blocksize: int):
                assert samplerate == 16_000
                return outer.recorder

        return Device()


async def test_stereo_loopback_becomes_mono_blocks() -> None:
    soundcard = FakeSoundcard()
    blocks = []
    async for block in loopback_blocks(soundcard):
        blocks.append(block)
        if len(blocks) == 3:
            break
    assert soundcard.asked == {"id": "Speakers", "include_loopback": True}
    assert all(block.shape == (1600,) and np.allclose(block, 0.3) for block in blocks)


async def test_a_capture_failure_stops_the_source_with_its_error() -> None:
    with pytest.raises(OSError, match="unplugged"):
        async for _block in loopback_blocks(FakeSoundcard(fail_after=2)):
            pass


@pytest.mark.parametrize("soundcard", [FakeSoundcard(speaker_name=None), FakeSoundcard(speaker_name="HDMI")])
async def test_missing_speakers_or_loopback_is_explained(soundcard) -> None:
    with pytest.raises(RuntimeError):
        async for _block in loopback_blocks(soundcard):
            pass
