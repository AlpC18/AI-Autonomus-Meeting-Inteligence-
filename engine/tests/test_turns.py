# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Speaker assignment: words and segments take the speaker they overlap most."""

from continuum.diarization.turns import SpeakerTurn, default_speaker, label_segment
from continuum.transcript import Segment, Word


def segment(*words: Word) -> Segment:
    return Segment(
        source="system",
        start=words[0].start,
        end=words[-1].end,
        text=" ".join(word.text for word in words),
        words=words,
        speaker="others",
    )


def test_words_take_the_speaker_of_the_overlapping_turn() -> None:
    turns = [SpeakerTurn(0.0, 1.0, "A"), SpeakerTurn(1.0, 3.0, "B")]
    labelled = label_segment(
        segment(Word("hi", 0.1, 0.4), Word("there", 1.2, 1.6), Word("friend", 1.7, 2.5)),
        turns,
    )

    assert [word.speaker for word in labelled.words] == ["A", "B", "B"]
    assert labelled.speaker == "B"


def test_word_straddling_two_turns_goes_to_the_larger_overlap() -> None:
    turns = [SpeakerTurn(0.0, 1.0, "A"), SpeakerTurn(1.0, 3.0, "B")]
    labelled = label_segment(segment(Word("okay", 0.9, 1.5)), turns)

    assert labelled.words[0].speaker == "B"


def test_segment_is_unchanged_when_no_turn_overlaps() -> None:
    original = segment(Word("hello", 5.0, 5.5))

    assert label_segment(original, [SpeakerTurn(0.0, 1.0, "A")]) == original


def test_default_speaker_comes_from_the_audio_source() -> None:
    assert default_speaker("mic") == "me"
    assert default_speaker("system") == "others"
