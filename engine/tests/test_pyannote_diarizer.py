# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The pyannote adapter converts pipeline output into turns on the stream timeline."""

from dataclasses import dataclass

import numpy as np
import pytest

pytest.importorskip("pyannote.audio")
from pyannote.core import Annotation
from pyannote.core import Segment as Span

from recall.audio.chunker import Utterance
from recall.diarization.pyannote_diarizer import PyannoteDiarizer
from recall.diarization.turns import SpeakerTurn


@dataclass
class Output:
    exclusive_speaker_diarization: Annotation


VOICES = {1.0: np.array([1.0, 0.0]), 2.0: np.array([0.0, 1.0])}


def _embed(samples: np.ndarray) -> np.ndarray:
    """Test audio is a constant per speaker; that constant picks the voice."""
    return VOICES[float(samples[0])]


def _replaying(*annotations: Annotation):
    runs = iter(annotations)
    return lambda audio: Output(next(runs))


def _annotation(*turns: tuple[float, float, str]) -> Annotation:
    annotation = Annotation()
    for start, end, speaker in turns:
        annotation[Span(start, end)] = speaker
    return annotation


def _utterance(start_s: float, *voices: tuple[float, float]) -> Utterance:
    """Build audio from (voice, seconds) parts played one after another."""
    parts = [np.full(int(seconds * 16_000), voice, dtype=np.float32) for voice, seconds in voices]
    return Utterance(start_s=start_s, samples=np.concatenate(parts))


def test_turns_are_offset_to_the_utterance_start() -> None:
    received = {}

    def pipeline(audio):
        received.update(audio)
        return Output(_annotation((0.0, 1.0, "SPEAKER_00"), (1.0, 2.5, "SPEAKER_01")))

    turns = PyannoteDiarizer(pipeline, _embed).diarize(_utterance(10.0, (1.0, 1.0), (2.0, 1.5)))

    assert turns == [SpeakerTurn(10.0, 11.0, "Speaker 1"), SpeakerTurn(11.0, 12.5, "Speaker 2")]
    assert received["sample_rate"] == 16_000
    assert tuple(received["waveform"].shape) == (1, 40_000)


def test_a_speaker_keeps_their_name_when_the_model_relabels_them() -> None:
    diarizer = PyannoteDiarizer(
        _replaying(
            _annotation((0.0, 2.0, "SPEAKER_00")),
            _annotation((0.0, 1.5, "SPEAKER_00"), (1.5, 3.5, "SPEAKER_01")),
        ),
        _embed,
    )

    first = diarizer.diarize(_utterance(10.0, (1.0, 2.0)))
    second = diarizer.diarize(_utterance(20.0, (2.0, 1.5), (1.0, 2.0)))

    assert first == [SpeakerTurn(10.0, 12.0, "Speaker 1")]
    assert second == [SpeakerTurn(20.0, 21.5, "Speaker 2"), SpeakerTurn(21.5, 23.5, "Speaker 1")]


def test_a_voice_is_judged_on_all_of_its_turns_in_the_utterance() -> None:
    heard = []

    def embed(samples: np.ndarray) -> np.ndarray:
        heard.append(len(samples) / 16_000)
        return _embed(samples)

    diarizer = PyannoteDiarizer(
        _replaying(
            _annotation((0.0, 0.6, "SPEAKER_00"), (0.6, 2.6, "SPEAKER_01"), (2.6, 3.2, "SPEAKER_00"))
        ),
        embed,
    )

    turns = diarizer.diarize(_utterance(0.0, (1.0, 0.6), (2.0, 2.0), (1.0, 0.6)))

    assert [turn.speaker for turn in turns] == ["Speaker 1", "Speaker 2", "Speaker 1"]
    assert heard == [1.2, 2.0]


def test_speech_too_short_to_recognise_is_left_unlabelled() -> None:
    diarizer = PyannoteDiarizer(
        _replaying(_annotation((0.0, 0.1, "SPEAKER_00"), (0.1, 2.1, "SPEAKER_01"))), _embed
    )

    turns = diarizer.diarize(_utterance(5.0, (2.0, 0.1), (1.0, 2.0)))

    assert turns == [SpeakerTurn(5.1, 7.1, "Speaker 1")]


def test_silence_gives_no_turns() -> None:
    diarizer = PyannoteDiarizer(_replaying(Annotation()), _embed)

    assert diarizer.diarize(_utterance(0.0, (1.0, 1.0))) == []


def test_a_named_voice_is_recognised_in_the_next_meeting(tmp_path) -> None:
    from recall.diarization.voices import VoiceBook

    one = _annotation((0.0, 2.0, "SPEAKER_00"))
    first = PyannoteDiarizer(_replaying(one), _embed, VoiceBook(tmp_path / "v.json"))
    first.diarize(_utterance(0.0, (2.0, 2.0)))
    assert first.recognise("Speaker 1") is None
    first.learn("Speaker 1", "Ayşe")
    first.learn("mic", "Me")  # no voice: nothing to remember

    later = PyannoteDiarizer(_replaying(one), _embed, VoiceBook(tmp_path / "v.json"))
    later.diarize(_utterance(0.0, (2.0, 2.0)))
    assert later.recognise("Speaker 1") == "Ayşe"
    assert PyannoteDiarizer(_replaying(), _embed).recognise("Speaker 1") is None


def test_two_known_voices_heard_as_one_are_split_again() -> None:
    diarizer = PyannoteDiarizer(
        _replaying(
            _annotation((0.0, 1.5, "SPEAKER_00"), (1.5, 3.0, "SPEAKER_01")),
            # The model hears the second utterance as a single speaker.
            _annotation((0.0, 4.0, "SPEAKER_00")),
            _annotation((0.0, 4.0, "SPEAKER_00")),
        ),
        _embed,
    )
    diarizer.diarize(_utterance(0.0, (1.0, 1.5), (2.0, 1.5)))

    mixed = diarizer.diarize(_utterance(10.0, (1.0, 2.0), (2.0, 2.0)))
    alone = diarizer.diarize(_utterance(20.0, (2.0, 4.0)))

    assert mixed == [SpeakerTurn(10.0, 12.0, "Speaker 1"), SpeakerTurn(12.0, 14.0, "Speaker 2")]
    assert alone == [SpeakerTurn(20.0, 24.0, "Speaker 2")]
