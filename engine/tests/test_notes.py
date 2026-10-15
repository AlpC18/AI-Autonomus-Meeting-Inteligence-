# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Transcripts rendered as Markdown notes and SRT subtitles."""

import stat
import wave
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from continuum.notes import MeetingNotes, clock, markdown_lines, speaker_runs, srt
from continuum.transcribe_cli import decode_audio, render
from continuum.transcript import Segment, Word

SOLO = Segment("mic", 3725.0, 3727.5, "The budget is  $35,000.", (), "me")
DUET = Segment(
    "system",
    10.0,
    14.0,
    "Hello there. Oh hello.",
    (
        Word("Hello", 10.0, 10.5, "Speaker 1"),
        Word("there.", 10.5, 11.0, "Speaker 1"),
        Word("Oh", 12.0, 12.2, "Speaker 2"),
        Word("hello.", 12.2, 13.0, None),
    ),
    "Speaker 2",
)


def test_a_segment_is_split_where_the_speaker_changes() -> None:
    assert speaker_runs(DUET) == [
        ("Speaker 1", 10.0, "Hello there."),
        ("Speaker 2", 12.0, "Oh hello."),
    ]
    assert speaker_runs(SOLO) == [("me", 3725.0, "The budget is  $35,000.")]


def test_times_are_written_as_clock_times() -> None:
    assert clock(3725.0) == "01:02:05"
    assert clock(3725.25, ",") == "01:02:05,250"


def test_markdown_has_one_line_per_speaker_turn() -> None:
    assert markdown_lines(DUET) == [
        "- `00:00:10` **Speaker 1:** Hello there.",
        "- `00:00:12` **Speaker 2:** Oh hello.",
    ]
    assert markdown_lines(SOLO) == ["- `01:02:05` **me:** The budget is $35,000."]


def test_srt_cues_follow_each_other_without_overlap() -> None:
    assert srt([DUET, SOLO]) == (
        "1\n00:00:10,000 --> 00:00:12,000\nSpeaker 1: Hello there.\n\n"
        "2\n00:00:12,000 --> 00:00:14,000\nSpeaker 2: Oh hello.\n\n"
        "3\n01:02:05,000 --> 01:02:07,500\nme: The budget is $35,000.\n"
    )


def test_plain_text_keeps_only_who_said_what() -> None:
    assert render([DUET], "txt") == "Speaker 1: Hello there.\nSpeaker 2: Oh hello.\n"


def test_notes_grow_line_by_line_in_a_private_file(tmp_path: Path) -> None:
    notes = MeetingNotes(tmp_path / "acme" / "website", datetime(2026, 10, 12, 9, 30, tzinfo=UTC))
    assert not notes.path.exists()

    notes.add(DUET)
    notes.add(SOLO)

    lines = notes.path.read_text(encoding="utf-8").splitlines()
    assert lines[:4] == ["---", 'title: "Meeting"', f"date: {notes_date(notes)}", "tags: [meeting]"]
    heading = lines.index("---", 1) + 2
    assert lines[heading].startswith("# Meeting — 2026-10-12")
    assert lines[heading + 2 :] == markdown_lines(DUET) + markdown_lines(SOLO)
    assert notes.path.suffix == ".md"
    assert stat.S_IMODE(notes.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(notes.path.parent.stat().st_mode) == 0o700


def notes_date(notes: MeetingNotes) -> str:
    return datetime(2026, 10, 12, 9, 30, tzinfo=UTC).astimezone().isoformat(timespec="seconds")


def test_notes_properties_are_valid_yaml_for_obsidian(tmp_path: Path) -> None:
    import yaml

    started = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
    notes = MeetingNotes(tmp_path, started, 'Q4 "Budget": Ayşe', attendees=("ana@acme.io",))
    notes.add(SOLO)

    _, front, _ = notes.path.read_text(encoding="utf-8").split("---\n", 2)
    properties = yaml.safe_load(front)
    assert properties["title"] == "Q4 Budget Ayşe"
    assert properties["tags"] == ["meeting"] and properties["attendees"] == ["ana@acme.io"]
    assert properties["date"] == started


def test_a_stereo_recording_is_read_as_mono_16_khz(tmp_path: Path) -> None:
    tone = (np.sin(np.linspace(0, 2000, 44_100)) * 20_000).astype(np.int16)
    with wave.open(str(tmp_path / "tone.wav"), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44_100)
        wav.writeframes(np.repeat(tone, 2).tobytes())

    samples = decode_audio(tmp_path / "tone.wav")

    assert samples.dtype == np.float32
    assert abs(len(samples) - 16_000) < 200
    assert 0.3 < float(np.abs(samples).max()) <= 1.0


def test_a_file_that_is_not_audio_is_refused(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not audio")

    with pytest.raises(Exception) as caught:
        decode_audio(tmp_path / "notes.txt")

    import av

    assert isinstance(caught.value, (av.FFmpegError, IndexError, ValueError))


def test_notes_never_reuse_an_existing_file(tmp_path) -> None:
    from datetime import UTC, datetime

    started = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
    first = MeetingNotes(tmp_path, started)
    first.add(SOLO)
    second = MeetingNotes(tmp_path, started)
    assert second.path != first.path and second.path.name.endswith("Meeting (2).md")
