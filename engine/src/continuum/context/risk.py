# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Risk tracking: promises with a date, and moments of doubt.

A statement that promises something by a date ("I'll have it done by
Friday") is a commitment. When a workload lookup is configured, the
speaker's open issues are counted and an overlay hint warns when the date
looks unrealistic. Phrases of doubt ("I'm not sure", "maybe") are marked.
Both are listed in the notes when the meeting ends. Matching is by phrase
lists (English only), not by an AI model, so nothing leaves the machine
unless the workload lookup is on.
"""

import calendar
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from continuum.notes import clock
from continuum.transcript import Segment

WARN_DUE = 3
"""Open issues already due by the promised date that make a promise risky."""

WARN_OPEN = 10
"""Open issues in total that make any dated promise risky."""

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_PROMISE = re.compile(
    r"\b(?:i'?ll|i will|we'?ll|we will|i can|we can|i'?m going to|we'?re going to|gonna|"
    r"will (?:be|have)|should be|can have|i promise|we promise|commit to)\b",
    re.IGNORECASE,
)
# ponytail: English phrases only; add other languages' phrases when meetings need them.
_DOUBT = re.compile(
    r"\b(?:not sure|i'?m unsure|i don'?t know|maybe|i guess|hopefully|i'?ll try|we'?ll try|"
    r"we'?ll see|hard to say|not convinced|not confident|i doubt|worried|concerned|"
    r"no idea|probably not|might not|i'?m afraid)\b",
    re.IGNORECASE,
)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


@dataclass(frozen=True, slots=True)
class Workload:
    """A person's open issues, and how many of them are due by a given date."""

    open: int
    due_by: int
    source: str


WorkloadLookup = Callable[[str, date], Workload | None]
"""``(speaker, due) -> workload``, or ``None`` when the person is unknown. May block."""


def _friday(day: date) -> date:
    return day + timedelta(days=max(0, 4 - day.weekday()))


def due_date(text: str, today: date) -> date | None:
    """The date ``text`` names, relative to ``today``, or ``None``."""
    lowered = text.lower()
    if match := _ISO.search(lowered):
        try:
            return date(*(int(part) for part in match.groups()))
        except ValueError:
            return None
    if re.search(r"\b(?:today|tonight|eod|end of (?:the )?day)\b", lowered):
        return today
    if re.search(r"\btomorrow\b", lowered):
        return today + timedelta(days=1)
    if re.search(r"\b(?:eow|this week|end of (?:the )?week)\b", lowered):
        return _friday(today)
    if re.search(r"\bnext week\b", lowered):
        return _friday(today + timedelta(days=7 - today.weekday()))
    if re.search(r"\bend of (?:the )?month\b", lowered):
        return today.replace(day=calendar.monthrange(today.year, today.month)[1])
    for index, name in enumerate(_WEEKDAYS):
        if re.search(rf"\b{name}\b", lowered):
            return today + timedelta(days=(index - today.weekday()) % 7 or 7)
    return None


@dataclass(frozen=True, slots=True)
class _Mark:
    at: float
    speaker: str
    text: str
    note: str

    def line(self) -> str:
        return f"- `{clock(self.at)}` **{self.speaker}:** {' '.join(self.text.split())} ({self.note})"


class RiskTracker:
    """Marks commitments and hesitations in a meeting; warns about risky promises live."""

    def __init__(self, today: Callable[[], date], workload: WorkloadLookup | None) -> None:
        self._today = today
        self._workload = workload
        self._commitments: list[_Mark] = []
        self._doubts: list[_Mark] = []

    def watch(self, segment: Segment) -> list[dict[str, Any]]:
        """Note ``segment``'s commitment or doubt; a hint when its promise looks unrealistic."""
        text, speaker = segment.text, segment.speaker
        if doubt := _DOUBT.search(text):
            self._doubts.append(_Mark(segment.start, speaker, text, doubt.group(0).lower()))
        if not _PROMISE.search(text):
            return []
        due = due_date(text, self._today())
        if due is None:
            return []
        self._commitments.append(_Mark(segment.start, speaker, text, f"due {due.isoformat()}"))
        load = self._workload(speaker, due) if self._workload is not None else None
        if load is None or (load.due_by < WARN_DUE and load.open < WARN_OPEN):
            return []
        return [
            {
                "kind": "commitment",
                "title": f"{speaker} promised a date: {due:%a %d %b}",
                "body": (
                    f"{speaker} has {load.open} open {load.source} issues, "
                    f"{load.due_by} due by then."
                ),
                "details": [" ".join(text.split())],
            }
        ]

    def finish(self) -> str | None:
        """The meeting's commitments and hesitations as Markdown; then start clean."""
        sections = []
        if self._commitments:
            sections.append("## Commitments\n\n" + "\n".join(mark.line() for mark in self._commitments))
        if self._doubts:
            sections.append("## Hesitations\n\n" + "\n".join(mark.line() for mark in self._doubts))
        self._commitments, self._doubts = [], []
        return "\n\n".join(sections) or None
