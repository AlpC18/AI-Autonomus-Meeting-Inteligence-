# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Decides whether a live statement contradicts what memory has on record."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from continuum.factcheck.figures import Figure, extract_figures, mask_figures
from continuum.memory.store import MemoryHit
from continuum.transcript import Segment

Search = Callable[[str, int], list[MemoryHit]]
"""Scoped memory search: ``(query, limit) -> hits``, best match first."""

DEFAULT_MIN_SCORE = 0.30
"""Similarity a past statement needs before it counts as the same topic.

Calibrated for the default embedding model on 17 English and Turkish pairs:
related statements scored 0.33-0.59, unrelated ones 0.03-0.23. Re-measure if
the embedding model changes.
"""


@dataclass(frozen=True, slots=True)
class FactCheckAlert:
    """A live statement that contradicts the record.

    For figures, ``claimed`` and ``recorded`` hold the conflicting values as
    they were spoken, for example ``("$50,000",)`` against ``("$35,000",)``.
    A contradiction judged by the AI model has no figures and says why in
    ``explanation``.
    """

    statement: str
    speaker: str
    claimed: tuple[str, ...]
    recorded: tuple[str, ...]
    record_text: str
    record_speaker: str
    record_spoken_at: datetime
    record_meeting_id: str
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy, used as the wire format."""
        return {**asdict(self), "record_spoken_at": self.record_spoken_at.isoformat()}


def _by_kind(figures: list[Figure]) -> dict[str, list[Figure]]:
    grouped: dict[str, list[Figure]] = {}
    for figure in figures:
        grouped.setdefault(figure.kind, []).append(figure)
    return grouped


class FactChecker:
    """Compares the figures in a statement with similar past statements.

    The rule: among past statements on the same topic that mention the same
    kind of figure (money, percent, a counted unit or a date), the most recent one is
    the record. If the live statement shares no value of that kind with the
    record, it is flagged. Statements without figures are never flagged, and
    are not even searched for, which keeps the common case free.
    """

    # ponytail: figures and dates only, so "we chose Stripe" against "we chose Paddle"
    # passes unnoticed, and two different budgets on a similar topic can be
    # flagged wrongly. An LLM judge over the same retrieved hits fixes both.
    def __init__(
        self, search: Search, *, min_score: float = DEFAULT_MIN_SCORE, candidates: int = 8
    ) -> None:
        self._search = search
        self._min_score = min_score
        self._candidates = candidates

    def check(self, segment: Segment) -> FactCheckAlert | None:
        """Return an alert if ``segment`` contradicts the record, else ``None``.

        Blocks while memory is searched; call it from a worker thread, and
        before the segment itself is stored so it cannot match itself.
        """
        claimed = _by_kind(extract_figures(segment.text))
        if not claimed:
            return None

        comparable = []
        # Search by topic only: with the figures left in, differing numbers push
        # otherwise identical statements apart and the record is not found.
        for hit in self._search(mask_figures(segment.text), self._candidates):
            # A claim that was itself flagged must never serve as the record.
            if hit.score < self._min_score or hit.disputed:
                continue
            recorded = _by_kind(extract_figures(hit.text))
            if claimed.keys() & recorded.keys():
                comparable.append((hit, recorded))
        if not comparable:
            return None

        record, recorded = max(comparable, key=lambda pair: pair[0].spoken_at)
        conflicting = [
            kind
            for kind in claimed.keys() & recorded.keys()
            if not {f.value for f in claimed[kind]} & {f.value for f in recorded[kind]}
        ]
        if not conflicting:
            return None
        return FactCheckAlert(
            statement=segment.text,
            speaker=segment.speaker,
            claimed=tuple(f.text for kind in sorted(conflicting) for f in claimed[kind]),
            recorded=tuple(f.text for kind in sorted(conflicting) for f in recorded[kind]),
            record_text=record.text,
            record_speaker=record.speaker,
            record_spoken_at=record.spoken_at,
            record_meeting_id=record.meeting_id,
        )
