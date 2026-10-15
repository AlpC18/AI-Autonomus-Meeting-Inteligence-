# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""What the user does during a live meeting: typed notes and speaker names.

Messages arrive from the desktop app over the local transcript socket and
are user input, so each is parsed and checked here before use.
"""

import json
import re
from dataclasses import dataclass, replace

from continuum.transcript import Segment

NOTE_SOURCE = "note"
"""``Segment.source`` of a typed note."""

NOTE_SPEAKER = "Note"
"""Speaker shown for a typed note; the summarizer treats these lines as the user's priorities."""

MAX_NOTE = 2000
MAX_NAME = 40

# Characters that would break the Markdown notes or the HUD layout.
_NAME_FORBIDDEN = re.compile(r"[\x00-\x1f\x7f*`_\[\]<>|#\\]")


@dataclass(frozen=True, slots=True)
class Note:
    """Text the user typed during the meeting."""

    text: str


@dataclass(frozen=True, slots=True)
class Rename:
    """Show speaker ``old`` as ``new`` from now on."""

    old: str
    new: str


@dataclass(frozen=True, slots=True)
class Ask:
    """A question about past meetings; ``request_id`` pairs it with its answer."""

    request_id: str
    question: str


@dataclass(frozen=True, slots=True)
class EndMeeting:
    """The user ended the meeting: summarise it and start a new one."""


@dataclass(frozen=True, slots=True)
class Brief:
    """The user asked for a brief on the current meeting from earlier ones."""


Command = Note | Rename | Ask | EndMeeting | Brief

MAX_QUESTION = 500
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def clean_name(value: object) -> str:
    """Return ``value`` as a speaker name.

    Raises:
        TypeError: if ``value`` is not text.
        ValueError: if it is empty, too long, uses Markdown symbols or is reserved.
    """
    if not isinstance(value, str):
        raise TypeError("a speaker name must be text")
    name = " ".join(value.split())
    if not 1 <= len(name) <= MAX_NAME or _NAME_FORBIDDEN.search(name):
        raise ValueError(f"a speaker name must be 1-{MAX_NAME} characters without Markdown symbols")
    if name.casefold() == NOTE_SPEAKER.casefold():
        raise ValueError(f"{NOTE_SPEAKER!r} is reserved for typed notes")
    return name


def parse(raw: str) -> Command | None:
    """Read one client message; ``None`` for anything malformed or unknown.

    Accepted: ``{"type": "note", "text": ...}``,
    ``{"type": "rename_speaker", "from": ..., "to": ...}``,
    ``{"type": "ask", "id": ..., "question": ...}`` and ``{"type": "end_meeting"}``.
    """
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(message, dict):
        return None
    if message.get("type") == "note":
        text = message.get("text")
        if not isinstance(text, str):
            return None
        # Keep line breaks out: a note is one line in the Markdown file.
        cleaned = " ".join("".join(ch for ch in text if ch.isprintable() or ch.isspace()).split())
        return Note(cleaned) if 0 < len(cleaned) <= MAX_NOTE else None
    if message.get("type") == "rename_speaker":
        try:
            old, new = clean_name(message.get("from")), clean_name(message.get("to"))
        except (TypeError, ValueError):
            return None
        return Rename(old, new) if old != new else None
    if message.get("type") == "ask":
        request_id, question = message.get("id"), message.get("question")
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            return None
        if not isinstance(question, str) or not 0 < len(question.strip()) <= MAX_QUESTION:
            return None
        return Ask(request_id, " ".join(question.split()))
    if message.get("type") == "end_meeting":
        return EndMeeting()
    if message.get("type") == "brief":
        return Brief()
    return None


class SpeakerNames:
    """Names the user gave to speakers, applied to every segment from now on.

    Renaming a name that was itself a rename updates the original label, so
    "Speaker 1" -> "Ana" -> "Ana K." keeps working. Not thread-safe: use it
    from the event loop only.
    """

    # ponytail: renames apply to what is said from now on; stored memory and
    # earlier note lines keep the old label (a note records the rename).
    def __init__(self) -> None:
        self._names: dict[str, str] = {}

    def rename(self, old: str, new: str) -> None:
        """Show every label currently displayed as ``old`` as ``new``."""
        labels = [label for label, shown in self._names.items() if shown == old]
        for label in labels or [old]:
            self._names[label] = new

    def named(self) -> dict[str, str]:
        """Every renamed label and the name it is shown as."""
        return dict(self._names)

    def shown(self, label: str) -> str:
        """How ``label`` is displayed now."""
        return self._names.get(label, label)

    def apply(self, segment: Segment) -> Segment:
        """Return ``segment`` with the user's names in place of raw labels."""
        if not self._names:
            return segment
        words = tuple(
            replace(word, speaker=self._names.get(word.speaker, word.speaker))
            if word.speaker is not None
            else word
            for word in segment.words
        )
        return replace(
            segment, speaker=self._names.get(segment.speaker, segment.speaker), words=words
        )


def note_segment(note: Note, at: float) -> Segment:
    """A typed note as a transcript segment at stream time ``at``."""
    return Segment(NOTE_SOURCE, at, at, note.text, (), NOTE_SPEAKER)
