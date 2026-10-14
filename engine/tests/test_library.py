# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Meeting library: reads only the notes folder; lines, search, playback, summary."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from continuum.library import Library, parse_lines
from continuum.llm import LlmSettings

NOTES = """# Budget sync

<!-- continuum:audio {audio} -->

- `00:00:04` **Speaker 1:** Last quarter we agreed on $50,000.
- `01:02:05` **Note:** Push back on the December date
not a transcript line

## Summary

Budget agreed.
"""


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    root = tmp_path / "notes"
    (root / "acme").mkdir(parents=True)
    audio = tmp_path / "budget.m4a"
    audio.write_bytes(b"audio")
    (root / "acme" / "budget.md").write_text(NOTES.format(audio=audio), encoding="utf-8")
    (root / "other.md").write_text("- `00:00:01` **me:** Launch plan is ready\n", encoding="utf-8")
    (tmp_path / "secret.md").write_text("outside", encoding="utf-8")
    return root


def test_lines_are_parsed_with_times_and_the_summary_is_left_out() -> None:
    lines = parse_lines(NOTES)
    assert [(line.time, line.speaker) for line in lines] == [(4, "Speaker 1"), (3725, "Note")]


def test_show_returns_lines_summary_and_existing_audio(folder: Path, tmp_path: Path) -> None:
    meeting = Library(folder).show(str(folder / "acme" / "budget.md"))

    assert meeting["title"] == "Budget sync"
    assert meeting["audio"] == str(tmp_path / "budget.m4a")
    assert str(meeting["summary"]).startswith("## Summary")
    assert len(meeting["lines"]) == 2


def test_missing_or_unplayable_audio_is_not_offered(folder: Path, tmp_path: Path) -> None:
    for target in (tmp_path / "gone.m4a", tmp_path / "secret.md"):
        notes = folder / "x.md"
        notes.write_text(NOTES.format(audio=target), encoding="utf-8")
        assert Library(folder).show(str(notes))["audio"] is None


@pytest.mark.parametrize(
    "path",
    ["{tmp}/secret.md", "{root}/../secret.md", "{root}/acme/budget.txt", "/etc/passwd"],
)
def test_files_outside_the_notes_folder_are_refused(folder: Path, tmp_path: Path, path: str) -> None:
    with pytest.raises((PermissionError, FileNotFoundError)):
        Library(folder).show(path.format(tmp=tmp_path, root=folder))


def test_symlink_out_of_the_folder_is_refused(folder: Path, tmp_path: Path) -> None:
    (folder / "link.md").symlink_to(tmp_path / "secret.md")
    with pytest.raises(PermissionError):
        Library(folder).show(str(folder / "link.md"))
    assert all(meeting.path != str(folder / "link.md") for meeting in Library(folder).meetings())


def test_list_and_search_across_meetings(folder: Path) -> None:
    library = Library(folder)
    assert {meeting.title for meeting in library.meetings()} == {"Budget sync", "other"}

    hits = library.search("BUDGET")
    assert [hit["text"] for hit in hits] == []  # the word is only in the title
    hits = library.search("quarter")
    assert [(hit["title"], hit["time"]) for hit in hits] == [("Budget sync", 4)]
    assert library.search("   ") == []


def test_summary_is_written_into_the_notes(folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeLlm:
        def complete(self, system: str, user: str) -> str:
            assert "Budget agreed." not in user  # the old summary is not resent
            return json.dumps({"overview": "New summary.", "decisions": [], "action_items": []})

    monkeypatch.setattr("continuum.library.connect", lambda settings: FakeLlm())
    notes = folder / "acme" / "budget.md"

    meeting = Library(folder).summarize(str(notes), LlmSettings("ollama", "m", "http://localhost:1/v1"))

    assert "New summary." in str(meeting["summary"])
    assert notes.read_text().count("## Summary") == 1


def test_cli_prints_json_and_errors(folder: Path) -> None:
    env = {**os.environ, "CONTINUUM_NOTES_DIR": str(folder), "CONTINUUM_TENANT_ID": "", "CONTINUUM_PROJECT_ID": ""}
    listed = subprocess.run(
        [sys.executable, "-m", "continuum.library", "list"], env=env, capture_output=True, text=True, check=False
    )
    assert listed.returncode == 0 and len(json.loads(listed.stdout)) == 2
    refused = subprocess.run(
        [sys.executable, "-m", "continuum.library", "show", "--", "/etc/passwd"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode == 1 and "error" in json.loads(refused.stdout)
