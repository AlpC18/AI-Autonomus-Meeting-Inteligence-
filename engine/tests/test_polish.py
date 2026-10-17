# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Polishing reads each speaker's passage on its own and keeps speakers, times and notes."""

import pytest

from recall.live_controls import NOTE_SOURCE
from recall.polish import MAX_PASSAGE_S, assemble, passages
from recall.transcript import Segment


def live(source: str, start: float, end: float, speaker: str, text: str = "(live)") -> Segment:
    return Segment(source, start, end, text, (), speaker)


# The recording started 98 s into the system stream and 45 s into the mic stream.
OFFSETS = {"system": 98.0, "mic": 45.0}


def test_consecutive_speech_of_one_speaker_is_one_passage_and_a_new_speaker_starts_another() -> None:
    segments = [
        live("system", 100.0, 103.0, "Speaker 1"),
        live("system", 103.5, 106.0, "Speaker 1"),
        live("system", 106.2, 108.0, "Speaker 2"),
        live("mic", 56.0, 58.0, "you"),
        live(NOTE_SOURCE, 101.0, 101.0, "note"),
    ]

    found = passages(segments, OFFSETS)

    assert [(p.start, p.end, [s.speaker for s in p.segments]) for p in found] == [
        (2.0, 8.0, ["Speaker 1", "Speaker 1"]),
        (pytest.approx(8.2), 10.0, ["Speaker 2"]),
        (11.0, 13.0, ["you"]),
    ]


def test_long_speech_and_long_pauses_start_new_passages() -> None:
    steady = [live("system", 98.0 + i * 5, 98.0 + i * 5 + 4.5, "Speaker 1") for i in range(8)]
    assert all(p.end - p.start <= MAX_PASSAGE_S for p in passages(steady, OFFSETS))
    paused = [live("system", 100.0, 101.0, "Speaker 1"), live("system", 110.0, 111.0, "Speaker 1")]
    assert len(passages(paused, OFFSETS)) == 2


def test_speech_from_before_the_recording_is_skipped() -> None:
    assert passages([live("system", 90.0, 95.0, "Speaker 1")], OFFSETS) == []


def test_accurate_lines_keep_the_passage_speaker_live_times_and_notes() -> None:
    first, second = live("system", 100.0, 104.0, "Speaker 1"), live("mic", 50.0, 53.0, "you")
    note = live(NOTE_SOURCE, 102.0, 102.0, "note", "check the budget")
    segments = [first, second, note]
    found = passages(segments, OFFSETS)
    # Passages come in recording order: the system line (2 s in) before the mic line (5 s in).
    lines = [[(2.1, 5.9, "Bütçe 35 bin dolara düşürüldü.")], [(5.2, 8.0, "Raporu cuma gününe kadar gönderiyorum.")]]

    result = assemble(found, lines, segments, OFFSETS, lambda label: {"Speaker 1": "Ayşe"}.get(label, label))

    assert [(p.segment.speaker, p.segment.text, p.segment.start) for p in result] == [
        ("you", "Raporu cuma gününe kadar gönderiyorum.", pytest.approx(50.2)),
        ("Ayşe", "Bütçe 35 bin dolara düşürüldü.", pytest.approx(100.1)),
        ("note", "check the budget", 102.0),
    ]
    assert [p.replaces for p in result] == [second, first, None]


def test_a_passage_that_came_back_empty_keeps_its_live_lines() -> None:
    segment = live("system", 100.0, 104.0, "Speaker 1", "Büyükçe düşürürdü")
    result = assemble(passages([segment], OFFSETS), [[]], [segment], OFFSETS)

    assert [p.segment for p in result] == [segment]
