# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Polishing reads each speaker's passage on its own and keeps speakers, times and notes."""

import pytest

from recall.live_controls import NOTE_SOURCE
from recall.polish import DEFAULT_VOICE, assemble, passages
from recall.transcript import Segment


def live(source: str, start: float, end: float, speaker: str, text: str = "(live)") -> Segment:
    return Segment(source, start, end, text, (), speaker)


# The recording started 98 s into the system stream and 45 s into the mic stream.
OFFSETS = {"system": 98.0, "mic": 45.0}


def test_each_speech_region_is_its_own_passage_with_the_speaker_it_overlaps() -> None:
    segments = [
        live("system", 100.0, 103.0, "Speaker 1"),
        live("system", 103.5, 106.0, "Speaker 1"),
        live("system", 106.2, 108.0, "Speaker 2"),
        live("mic", 56.0, 58.0, "you"),
        live(NOTE_SOURCE, 101.0, 101.0, "note"),
    ]
    regions = [(2.0, 5.0), (5.5, 8.0), (8.2, 10.0), (11.0, 13.0)]

    found = passages(regions, segments, OFFSETS)

    # Not merged, even for one speaker: one person may switch language between sentences.
    assert [(p.start, p.end, p.speaker, len(p.segments)) for p in found] == [
        (2.0, 5.0, "Speaker 1", 1),
        (5.5, 8.0, "Speaker 1", 1),
        (8.2, 10.0, "Speaker 2", 1),
        (11.0, 13.0, "you", 1),
    ]


def test_speech_the_live_transcript_missed_gets_the_nearest_speaker() -> None:
    segments = [live("system", 100.0, 103.0, "Speaker 1"), live("mic", 75.0, 76.0, "you")]

    found = passages([(6.0, 7.0), (29.0, 30.5)], segments, OFFSETS)

    assert [(p.speaker, p.segments) for p in found] == [("Speaker 1", ()), ("you", (segments[1],))]
    assert passages([(1.0, 2.0)], [], OFFSETS)[0].speaker == DEFAULT_VOICE[1]


def test_accurate_lines_keep_the_passage_speaker_live_times_and_notes() -> None:
    first, second = live("system", 100.0, 104.0, "Speaker 1"), live("mic", 50.0, 53.0, "you")
    note = live(NOTE_SOURCE, 102.0, 102.0, "note", "check the budget")
    segments = [first, second, note]
    found = passages([(2.0, 6.0), (5.0, 8.0)], segments, OFFSETS)
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
    result = assemble(passages([(2.0, 6.0)], [segment], OFFSETS), [[]], [segment], OFFSETS)

    assert [p.segment for p in result] == [segment]


def test_speech_only_the_accurate_model_heard_is_added() -> None:
    segment = live("system", 100.0, 103.0, "Speaker 1")
    found = passages([(2.0, 5.0), (6.0, 9.0)], [segment], OFFSETS)
    lines = [[(2.0, 5.0, "Buxheti u ul.")], [(6.0, 9.0, "Na duhen dy zhvillues.")]]

    result = assemble(found, lines, [segment], OFFSETS)

    assert [(p.segment.text, p.replaces) for p in result] == [("Buxheti u ul.", segment), ("Na duhen dy zhvillues.", None)]


def test_an_unsure_stretch_is_read_again_in_the_language_before_it() -> None:
    import numpy as np

    from recall.polish import Reading, transcribe_passages

    calls: list[tuple[int, str | None]] = []

    def read(samples, language):
        index = int(samples[0])
        calls.append((index, language))
        if index == 1 and language is None:
            return Reading([(0.0, 1.0, "to a go-a-i-report nda")], "en", False)
        if index == 1:
            return Reading([(0.0, 1.0, "Arta do të dërgoj raportin.")], language, True)
        if index == 2:
            return Reading([(0.0, 1.0, ",")], "en", False)
        return Reading([(0.0, 1.0, "Buxheti u ul.")], "sq", True)

    audio = np.concatenate([np.full(16_000, value, dtype=np.float32) for value in (0, 1, 2)])
    lines = transcribe_passages(audio, [(0.5, 0.6), (1.5, 1.6), (2.5, 2.6)], read)

    assert [[text for _, _, text in passage] for passage in lines] == [
        ["Buxheti u ul."],
        ["Arta do të dërgoj raportin."],
        [],  # still unsure: the live lines are kept instead
    ]
    assert calls == [(0, None), (1, None), (1, "sq"), (2, None), (2, "sq")]


def test_confidence_rejects_stray_letters_and_unlikely_text() -> None:
    from recall.polish import confident

    assert confident([("Klienti kërkon një zbritje.", -0.2, 1.3)])
    assert not confident([("to a go", -0.3, 1.2), (",", -0.3, 1.0), ("t", -0.3, 1.0), ("k", -0.3, 1.0)])
    assert not confident([("Bugjeti uull", -1.6, 1.2)])
    assert not confident([("ja ja ja ja ja ja ja ja ja", -0.2, 3.1)])


def test_the_redo_runs_in_its_own_process() -> None:
    import os

    from recall.polish import in_own_process

    assert in_own_process(os.getpid)() != os.getpid()


def test_short_stretches_are_joined_to_the_closer_neighbour() -> None:
    from recall.polish import join_short

    assert join_short([(0.0, 3.0), (3.4, 3.8), (5.5, 9.0)]) == [(0.0, 3.8), (5.5, 9.0)]
    assert join_short([(0.0, 3.0), (6.0, 6.5), (9.0, 12.0)]) == [(0.0, 3.0), (6.0, 6.5), (9.0, 12.0)]
    assert join_short([(0.0, 0.4), (0.6, 1.0), (1.2, 4.0)]) == [(0.0, 4.0)]


def test_the_redo_waits_while_live_transcription_runs() -> None:
    import multiprocessing
    import threading

    from recall.polish import _wait_turn, in_own_process

    live_idle = multiprocessing.get_context("spawn").Event()  # cleared: live is transcribing
    done = threading.Event()
    worker = threading.Thread(target=lambda: (in_own_process(_wait_turn, live_idle)(), done.set()))
    worker.start()

    assert not done.wait(2.0)
    live_idle.set()
    assert done.wait(30.0)
    worker.join()


def test_the_most_likely_meeting_language_is_chosen() -> None:
    from recall.polish import most_likely

    probabilities = {"ru": 0.6, "sq": 0.3, "en": 0.1}
    assert most_likely(probabilities, ("en", "tr", "de", "it", "sq")) == "sq"
    assert most_likely(probabilities, ()) is None


def test_a_repetition_loop_is_not_trusted_even_when_the_model_says_so() -> None:
    from recall.polish import confident

    assert not confident([("sticks e jine nike " + "nene " * 80, -0.3, 1.5)])
