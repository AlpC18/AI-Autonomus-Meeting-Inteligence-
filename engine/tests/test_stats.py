# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Speaker statistics: talk time, longest turn and interruptions."""

from continuum.live_controls import NOTE_SOURCE
from continuum.stats import speaker_stats, to_markdown, turns
from continuum.transcript import Segment, Word


def words(source: str, *spoken: tuple[str, float, float]) -> Segment:
    items = tuple(Word("w", start, end, speaker) for speaker, start, end in spoken)
    return Segment(source, items[0].start, items[-1].end, "w " * len(items), items, spoken[0][0])


def test_one_speakers_words_across_segments_form_one_turn() -> None:
    first = words("system", ("Ana", 0.0, 5.0), ("Ana", 5.5, 15.0))
    second = words("system", ("Ana", 15.5, 30.0), ("Mark", 31.0, 40.0))
    assert turns([first, second]) == [("Ana", 0.0, 30.0), ("Mark", 31.0, 40.0)]


def test_talk_time_share_longest_turn_and_interruptions() -> None:
    ana = words("system", ("Ana", 0.0, 30.0), ("Ana", 50.0, 60.0))
    me = words("mic", ("Me", 20.0, 35.0), ("Me", 61.0, 62.0))  # starts while Ana is talking
    note = Segment(NOTE_SOURCE, 25.0, 25.0, "a note", (), "Note")

    stats = speaker_stats([ana, me, note])

    assert [(s.speaker, s.talk_s, s.longest_s, s.interruptions) for s in stats] == [
        ("Ana", 40.0, 30.0, 0),
        ("Me", 16.0, 15.0, 1),
    ]
    assert round(sum(s.share for s in stats), 6) == 1.0


def test_a_turn_right_after_another_is_not_an_interruption() -> None:
    stats = speaker_stats([words("system", ("Ana", 0.0, 10.0), ("Mark", 10.2, 20.0))])
    assert [s.interruptions for s in stats] == [0, 0]


def test_markdown_table() -> None:
    table = to_markdown(speaker_stats([words("system", ("Ana", 0.0, 90.0))]))
    assert table.startswith("## Talk time\n")
    assert "| Ana | 00:01:30 | 100% | 00:01:30 | 0 |" in table
    assert to_markdown([]).rstrip().endswith("|---|---|---|---|---|")
