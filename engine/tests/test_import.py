# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Recordings from disk: subtitles, a watched folder, and import into memory."""

import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from continuum.notes import vtt
from continuum.transcribe_cli import AUDIO_MARKER, meeting_for, render, watch
from continuum.transcript import Segment, Word

DUET = Segment(
    "system",
    10.0,
    14.0,
    "Hello there. Oh <hello>.",
    (
        Word("Hello", 10.0, 10.5, "Speaker 1"),
        Word("there.", 10.5, 11.0, "Speaker 1"),
        Word("Oh", 12.0, 12.2, "Speaker 2"),
        Word("<hello>.", 12.2, 13.0, None),
    ),
    "Speaker 2",
)


def test_vtt_has_voice_tags_and_escaped_text() -> None:
    assert vtt([DUET]) == (
        "WEBVTT\n\n"
        "00:00:10.000 --> 00:00:12.000\n<v Speaker 1>Hello there.\n\n"
        "00:00:12.000 --> 00:00:14.000\n<v Speaker 2>Oh &lt;hello&gt;.\n"
    )


def test_markdown_from_a_recording_names_it_for_playback(tmp_path: Path) -> None:
    recording = tmp_path / "Weekly sync.m4a"
    text = render([DUET], "md", recording)
    assert text.startswith(f"# Weekly sync\n\n{AUDIO_MARKER}{recording.resolve()} -->\n\n- `00:00:10`")
    tricky = tmp_path / "a-->b.wav"
    assert AUDIO_MARKER not in render([DUET], "md", tricky)


def test_same_recording_maps_to_the_same_meeting(tmp_path: Path) -> None:
    first, copy, other = tmp_path / "a.wav", tmp_path / "b.wav", tmp_path / "c.wav"
    first.write_bytes(b"same audio")
    copy.write_bytes(b"same audio")
    other.write_bytes(b"other audio")
    when = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)

    assert meeting_for(first, when) == meeting_for(copy, when)
    assert meeting_for(first, when).meeting_id != meeting_for(other, when).meeting_id
    assert meeting_for(first, None).started_at.tzinfo is not None


def test_watcher_waits_for_a_finished_file_and_does_each_once(tmp_path: Path) -> None:
    (tmp_path / "meeting.m4a").write_bytes(b"x" * 10)
    (tmp_path / "notes.txt").write_text("not a recording")
    (tmp_path / "broken.wav").write_bytes(b"y")
    done: set[Path] = set()
    calls: list[str] = []

    def transcribe(path: Path) -> list[Segment]:
        calls.append(path.name)
        if path.name == "broken.wav":
            raise ValueError("cannot decode")
        return [DUET]

    watch(tmp_path, transcribe, lambda path, _segments: done.add(path), lambda path: path in done, 0, rounds=4)

    # First scan only notes the sizes; the broken file is tried once, never again.
    assert sorted(calls) == ["broken.wav", "meeting.m4a"]
    assert done == {tmp_path / "meeting.m4a"}


def test_a_file_still_growing_is_not_transcribed(tmp_path: Path) -> None:
    growing = tmp_path / "live.wav"
    calls: list[str] = []

    def transcribe(path: Path) -> list[Segment]:
        calls.append(path.name)
        return []

    for size in range(1, 4):
        growing.write_bytes(b"x" * size)
        watch(tmp_path, transcribe, lambda *_: None, lambda _path: False, 0, rounds=1)
    assert calls == []


@pytest.mark.skipif(shutil.which("say") is None, reason="needs macOS say")
def test_cli_imports_a_recording_into_memory_and_writes_vtt(tmp_path: Path) -> None:
    recording = tmp_path / "standup.aiff"
    subprocess.run(
        ["say", "-o", str(recording), "The launch budget is forty thousand dollars."], check=True
    )
    env = {
        **os.environ,
        "CONTINUUM_TENANT_ID": "acme",
        "CONTINUUM_PROJECT_ID": "imports",
        "CONTINUUM_MEMORY_DIR": str(tmp_path / "memory"),
        "CONTINUUM_WHISPER_MODEL": "tiny",
        "CONTINUUM_ASR_BACKEND": "faster-whisper",
        "HF_TOKEN": "",
    }
    command = [sys.executable, "-m", "continuum.transcribe_cli", str(recording), "--remember"]
    for _ in range(2):  # importing twice must not duplicate the meeting
        result = subprocess.run(
            [*command, "--format", "vtt", "--output", str(tmp_path / "out" / "standup.vtt")],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    assert (tmp_path / "out" / "standup.vtt").read_text().startswith("WEBVTT")
    search = subprocess.run(
        [sys.executable, "-m", "continuum.memory.cli", "launch budget", "--limit", "10"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert search.returncode == 0, search.stderr
    assert search.stdout.lower().count("budget") == 1
