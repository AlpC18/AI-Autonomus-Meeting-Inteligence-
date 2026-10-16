# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Plain-text renderings of a transcript: Markdown notes, SRT and WebVTT subtitles.

Markdown notes are ordinary files, so they open in any editor and sync with
Obsidian or Git without this app.
"""

import logging
from datetime import datetime
from pathlib import Path

from continuum.transcript import Segment

logger = logging.getLogger(__name__)


def speaker_runs(segment: Segment) -> list[tuple[str, float, str]]:
    """Split ``segment`` into ``(speaker, start, text)`` runs in spoken order.

    Consecutive words by one speaker form a run; words with no speaker of
    their own count as the segment's speaker. A segment with one voice, or
    without word timings, is a single run holding the segment's own text.
    """
    runs: list[tuple[str, float, list[str]]] = []
    for word in segment.words:
        speaker = word.speaker or segment.speaker
        if runs and runs[-1][0] == speaker:
            runs[-1][2].append(word.text.strip())
        else:
            runs.append((speaker, word.start, [word.text.strip()]))
    if len(runs) < 2:
        return [(segment.speaker, segment.start, segment.text)]
    return [(speaker, start, " ".join(words)) for speaker, start, words in runs]


def clock(seconds: float, millis_separator: str | None = None) -> str:
    """Format a stream time as ``HH:MM:SS``, or ``HH:MM:SS,mmm`` for SRT."""
    whole = int(seconds * 1000)
    hours, rest = divmod(whole, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    stamp = f"{hours:02}:{minutes:02}:{secs:02}"
    return stamp if millis_separator is None else f"{stamp}{millis_separator}{millis:03}"


def markdown_lines(segment: Segment) -> list[str]:
    """Return one Markdown list item per speaker run in ``segment``."""
    return [
        f"- `{clock(start)}` **{speaker}:** {' '.join(text.split())}"
        for speaker, start, text in speaker_runs(segment)
    ]


def _cues(segments: list[Segment]) -> list[tuple[float, float, str, str]]:
    """``(start, end, speaker, text)`` per speaker run; a run ends where the next one starts."""
    runs = [
        (start, segment.end, speaker, " ".join(text.split()))
        for segment in segments
        for speaker, start, text in speaker_runs(segment)
    ]
    cues = []
    for index, (start, segment_end, speaker, text) in enumerate(runs):
        same_segment_next = index + 1 < len(runs) and runs[index + 1][1] == segment_end
        end = runs[index + 1][0] if same_segment_next else segment_end
        cues.append((start, max(end, start), speaker, text))
    return cues


def srt(segments: list[Segment]) -> str:
    """Render ``segments`` as SubRip subtitles, one cue per speaker run."""
    return "\n".join(
        f"{index}\n{clock(start, ',')} --> {clock(end, ',')}\n{speaker}: {text}\n"
        for index, (start, end, speaker, text) in enumerate(_cues(segments), start=1)
    )


def vtt(segments: list[Segment]) -> str:
    """Render ``segments`` as WebVTT subtitles with voice tags, one cue per speaker run."""
    cues = "\n".join(
        f"{clock(start, '.')} --> {clock(end, '.')}\n<v {_vtt_safe(speaker)}>{_vtt_safe(text)}\n"
        for start, end, speaker, text in _cues(segments)
    )
    return "WEBVTT\n\n" + cues


def _vtt_safe(text: str) -> str:
    """Escape the characters that WebVTT cue text treats as markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class MeetingNotes:
    """Writes one meeting's transcript to a Markdown file as it is spoken.

    Each line is appended and flushed immediately, so the file is complete up
    to the last sentence even if the app is killed. The file is created on
    the first segment, so a session in which nobody speaks leaves nothing.
    """

    def __init__(self, directory: Path, started_at: datetime, title: str = "Meeting") -> None:
        """``started_at`` must be timezone-aware; it names the file."""
        local = started_at.astimezone()
        self._heading = f"# {title} — {local:%Y-%m-%d %H:%M}\n\n"
        self.path = directory / f"{local:%Y-%m-%d %H%M%S} {title}.md"
        """Where the notes are (or will be) written."""

    def add(self, segment: Segment) -> None:
        """Append ``segment`` to the file, creating folder and file if needed.

        Raises:
            OSError: if the folder or file cannot be written.
        """
        new = not self.path.exists()
        # Transcripts are private: only the current user may read them.
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            if new:
                self.path.chmod(0o600)
                file.write(self._heading)
            file.write("\n".join(markdown_lines(segment)) + "\n")
