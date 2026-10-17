# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Assigns speakers to transcript segments from diarization turns."""

from collections import defaultdict
from dataclasses import dataclass, replace

from recall.transcript import Segment, Word

_SOURCE_SPEAKERS = {"mic": "me", "system": "others", "tab": "others"}


@dataclass(frozen=True, slots=True)
class SpeakerTurn:
    """A span of time during which one speaker is talking."""

    start: float
    end: float
    speaker: str


def default_speaker(source: str) -> str:
    """Return the speaker label implied by the audio source alone.

    The microphone is the local user and system audio is everyone else. This
    is the label used when no diarization model has run. Unknown sources are
    returned unchanged.
    """
    return _SOURCE_SPEAKERS.get(source, source)


def _overlap(start: float, end: float, turn: SpeakerTurn) -> float:
    return max(0.0, min(end, turn.end) - max(start, turn.start))


def _speaker_for(word: Word, turns: list[SpeakerTurn]) -> str | None:
    best = max(turns, key=lambda turn: _overlap(word.start, word.end, turn), default=None)
    if best is not None and _overlap(word.start, word.end, best) > 0.0:
        return best.speaker
    # Whisper gives some words no duration; those are placed by their start time.
    return next((turn.speaker for turn in turns if turn.start <= word.start <= turn.end), None)


def label_segment(segment: Segment, turns: list[SpeakerTurn]) -> Segment:
    """Return a copy of ``segment`` with speakers taken from ``turns``.

    Each word gets the speaker of the turn it overlaps most. The segment's
    speaker becomes whoever spoke for the longest total time within it. Words
    that overlap no turn keep their existing speaker, and a segment with no
    overlapping turn at all is returned unchanged.
    """
    words = tuple(
        replace(word, speaker=_speaker_for(word, turns) or word.speaker)
        for word in segment.words
    )
    spoken: defaultdict[str, float] = defaultdict(float)
    for word in segment.words:
        speaker = _speaker_for(word, turns)
        if speaker is not None:
            spoken[speaker] += word.end - word.start
    if not spoken:
        return segment
    return replace(segment, words=words, speaker=max(spoken, key=spoken.__getitem__))
