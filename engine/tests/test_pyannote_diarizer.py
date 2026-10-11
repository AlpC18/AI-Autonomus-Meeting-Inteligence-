# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The pyannote adapter converts pipeline output into turns on the stream timeline."""

from dataclasses import dataclass

import numpy as np
import pytest

pytest.importorskip("pyannote.audio")
from pyannote.core import Annotation  # noqa: E402
from pyannote.core import Segment as Span  # noqa: E402

from continuum.audio.chunker import Utterance  # noqa: E402
from continuum.diarization.pyannote_diarizer import PyannoteDiarizer  # noqa: E402
from continuum.diarization.turns import SpeakerTurn  # noqa: E402


@dataclass
class Output:
    exclusive_speaker_diarization: Annotation


def test_turns_are_offset_to_the_utterance_start() -> None:
    annotation = Annotation()
    annotation[Span(0.0, 1.0)] = "SPEAKER_00"
    annotation[Span(1.0, 2.5)] = "SPEAKER_01"
    received = {}

    def pipeline(audio):
        received.update(audio)
        return Output(annotation)

    utterance = Utterance(start_s=10.0, samples=np.zeros(16_000, dtype=np.float32))
    turns = PyannoteDiarizer(pipeline).diarize(utterance)

    assert turns == [
        SpeakerTurn(10.0, 11.0, "SPEAKER_00"),
        SpeakerTurn(11.0, 12.5, "SPEAKER_01"),
    ]
    assert received["sample_rate"] == 16_000
    assert tuple(received["waveform"].shape) == (1, 16_000)
