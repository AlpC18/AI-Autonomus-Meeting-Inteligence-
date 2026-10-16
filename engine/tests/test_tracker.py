# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""A voice heard again gets the name it was given the first time."""

import numpy as np

from continuum.diarization.tracker import SpeakerTracker

ANNA = np.array([1.0, 0.0, 0.0])
BORIS = np.array([0.0, 1.0, 0.0])
ANNA_AGAIN = np.array([0.9, 0.3, 0.1])  # cosine 0.94 with ANNA, 0.31 with BORIS


def test_speakers_are_numbered_in_the_order_they_are_first_heard() -> None:
    tracker = SpeakerTracker()

    assert tracker.name(ANNA, 3.0) == "Speaker 1"
    assert tracker.name(BORIS, 3.0) == "Speaker 2"


def test_a_voice_heard_again_keeps_its_name() -> None:
    tracker = SpeakerTracker()
    tracker.name(ANNA, 3.0)
    tracker.name(BORIS, 3.0)

    assert tracker.name(ANNA_AGAIN, 3.0) == "Speaker 1"
    assert tracker.name(BORIS * 7.0, 3.0) == "Speaker 2"


def test_short_speech_can_match_but_never_adds_a_speaker() -> None:
    tracker = SpeakerTracker()
    tracker.name(ANNA, 3.0)

    assert tracker.name(ANNA_AGAIN, 0.4) == "Speaker 1"
    assert tracker.name(BORIS, 0.4) is None
    assert tracker.name(BORIS, 3.0) == "Speaker 2"


def test_short_speech_does_not_change_what_a_speaker_sounds_like() -> None:
    tracker = SpeakerTracker(match=0.9)
    tracker.name(ANNA, 3.0)
    drifted = np.array([0.92, 0.39, 0.0])  # matches ANNA, pulls the average if learned

    for _ in range(50):
        tracker.name(drifted, 0.4)

    assert tracker.name(np.array([0.8, 0.6, 0.0]), 3.0) == "Speaker 2"


def test_the_remembered_voice_follows_the_clips_matched_to_it() -> None:
    tracker = SpeakerTracker(match=0.9)
    tracker.name(ANNA, 3.0)
    for _ in range(50):
        tracker.name(np.array([0.92, 0.39, 0.0]), 3.0)

    assert tracker.name(np.array([0.8, 0.6, 0.0]), 3.0) == "Speaker 1"


def test_unusable_embeddings_get_no_name() -> None:
    tracker = SpeakerTracker()

    assert tracker.name(np.array([np.nan, 1.0, 0.0]), 3.0) is None
    assert tracker.name(np.zeros(3), 3.0) is None
    assert tracker.name(ANNA, 3.0) == "Speaker 1"
