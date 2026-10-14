# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The meeting library: past meetings' Markdown notes, for the desktop viewer.

``continuum-library`` lists, reads, searches and summarises the notes in
``CONTINUUM_NOTES_DIR`` and prints JSON. It only ever touches files inside
that folder, whatever path it is given, and only reports a recording for
playback when the notes name an existing audio or video file.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from continuum.config import Settings
from continuum.llm import LlmSettings, connect
from continuum.summarize_cli import split_summary
from continuum.summary import summarize, to_markdown

_LINE = re.compile(r"^- `(\d{2}):(\d{2}):(\d{2})` \*\*(.+?):\*\* (.*)$")
_AUDIO = re.compile(r"^<!-- continuum:audio (.+) -->$")
_PLAYABLE = frozenset({".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aiff", ".aif", ".webm", ".mp4", ".mov"})
SUMMARY_HEADING = "## Summary"
MAX_MEETINGS = 500
MAX_RESULTS = 200


@dataclass(frozen=True, slots=True)
class Line:
    """One transcript line: seconds from the start, who spoke, what they said."""

    time: float
    speaker: str
    text: str


@dataclass(frozen=True, slots=True)
class MeetingFile:
    """A meeting in the list."""

    path: str
    title: str
    modified: str
    has_summary: bool


def title_of(text: str, path: Path) -> str:
    """The first Markdown heading, or the file name."""
    heading = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), "")
    return heading or path.stem


def parse_lines(text: str) -> list[Line]:
    """Transcript lines of a notes file, ignoring everything else (summary, comments)."""
    lines = []
    for raw in text.split(f"\n{SUMMARY_HEADING}\n", 1)[0].splitlines():
        match = _LINE.match(raw)
        if match:
            hours, minutes, seconds, speaker, said = match.groups()
            lines.append(Line(int(hours) * 3600 + int(minutes) * 60 + int(seconds), speaker, said))
    return lines


def summary_of(text: str) -> str | None:
    """The summary section written by the summarizer, if any."""
    parts = text.split(f"\n{SUMMARY_HEADING}\n", 1)
    return f"{SUMMARY_HEADING}\n{parts[1]}".strip() if len(parts) == 2 else None


def audio_of(text: str) -> str | None:
    """The recording named in the notes, if it exists and can be played."""
    for raw in text.splitlines()[:10]:
        match = _AUDIO.match(raw.strip())
        if match:
            path = Path(match.group(1))
            if path.is_absolute() and path.suffix.lower() in _PLAYABLE and path.is_file():
                return str(path)
    return None


class Library:
    """Read access to one notes folder."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def resolve(self, path: str) -> Path:
        """Return ``path`` as a notes file inside the folder.

        Raises:
            PermissionError: if it points outside the folder or is not Markdown.
            FileNotFoundError: if there is no such file.
        """
        candidate = Path(path).expanduser().resolve()
        if not candidate.is_relative_to(self._root) or candidate.suffix.lower() != ".md":
            raise PermissionError("Only Markdown notes inside the notes folder can be opened.")
        if not candidate.is_file():
            raise FileNotFoundError(f"No such meeting: {candidate.name}")
        return candidate

    def files(self) -> list[Path]:
        """Notes files, newest first."""
        if not self._root.is_dir():
            return []
        found = [path for path in self._root.rglob("*.md") if path.is_file() and not path.is_symlink()]
        return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)[:MAX_MEETINGS]

    def meetings(self) -> list[MeetingFile]:
        """The list shown in the viewer."""
        result = []
        for path in self.files():
            text = path.read_text(encoding="utf-8", errors="replace")
            modified = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
            result.append(MeetingFile(str(path), title_of(text, path), modified, summary_of(text) is not None))
        return result

    def show(self, path: str) -> dict[str, object]:
        """One meeting: title, lines, summary and playable recording."""
        file = self.resolve(path)
        text = file.read_text(encoding="utf-8", errors="replace")
        return {
            "path": str(file),
            "title": title_of(text, file),
            "audio": audio_of(text),
            "summary": summary_of(text),
            "lines": [asdict(line) for line in parse_lines(text)],
        }

    def search(self, query: str) -> list[dict[str, object]]:
        """Lines containing ``query`` (any case) across all meetings, newest meeting first."""
        needle = query.casefold().strip()
        if not needle:
            return []
        results: list[dict[str, object]] = []
        for path in self.files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in parse_lines(text):
                if needle in line.text.casefold() or needle in line.speaker.casefold():
                    results.append({"path": str(path), "title": title_of(text, path), **asdict(line)})
                    if len(results) >= MAX_RESULTS:
                        return results
        return results

    def summarize(self, path: str, llm_settings: LlmSettings) -> dict[str, object]:
        """Summarise one meeting with the configured model and save it into the notes."""
        file = self.resolve(path)
        text = file.read_text(encoding="utf-8")
        body = split_summary(text)
        summary = summarize(body, connect(llm_settings), today=date.today())
        file.write_text(body + "\n" + to_markdown(summary), encoding="utf-8")
        return self.show(str(file))


def main() -> None:
    """Entry point of ``continuum-library`` (used by the desktop app; prints JSON).

    Commands: ``list``, ``show PATH``, ``search QUERY``, ``summarize PATH``.
    Errors are printed as ``{"error": ...}`` with exit code 1.
    """
    parser = argparse.ArgumentParser(description="Read past meetings' notes (JSON output).")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    for name in ("show", "summarize"):
        commands.add_parser(name).add_argument("path")
    commands.add_parser("search").add_argument("query")
    args = parser.parse_args()

    def fail(message: str) -> None:
        sys.stdout.write(json.dumps({"error": message}) + "\n")
        sys.exit(1)

    try:
        settings = Settings.from_env(os.environ)
    except ValueError as error:
        fail(f"Invalid configuration: {error}")
        return
    if settings.notes_dir is None:
        fail("Set CONTINUUM_NOTES_DIR to keep meeting notes; the library reads them from there.")
        return
    directory = settings.notes_dir
    if settings.scope is not None:
        directory = directory / settings.scope.tenant_id / settings.scope.project_id
    library = Library(directory)
    try:
        if args.command == "list":
            result: object = [asdict(meeting) for meeting in library.meetings()]
        elif args.command == "show":
            result = library.show(args.path)
        elif args.command == "search":
            result = library.search(args.query)
        else:
            llm_settings = LlmSettings.from_env(os.environ)
            if llm_settings is None:
                fail("No AI model is configured: set CONTINUUM_LLM_PROVIDER (see engine/.env.example).")
                return
            result = library.summarize(args.path, llm_settings)
    except (PermissionError, FileNotFoundError, ValueError, RuntimeError, OSError) as error:
        fail(str(error))
        return
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
