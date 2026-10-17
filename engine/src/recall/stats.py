# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Who talked how much: talk time, longest turn and interruptions per speaker.

Computed from the word timings the transcript already has, so it costs no
AI call and works offline. Typed notes are not speech and are ignored.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from recall.language import t
from recall.live_controls import NOTE_SOURCE
from recall.notes import clock
from recall.transcript import Segment

PAUSE_S = 2.0
"""A speaker's turns closer than this count as one continuous turn."""

OVERLAP_S = 0.5
"""How far a turn must start inside someone else's to count as an interruption."""


@dataclass(frozen=True, slots=True)
class SpeakerStats:
    """One speaker's share of a meeting (times in seconds)."""

    speaker: str
    talk_s: float
    share: float
    longest_s: float
    interruptions: int


def turns(segments: Iterable[Segment]) -> list[tuple[str, float, float]]:
    """Return ``(speaker, start, end)`` turns in time order, joining short pauses."""
    pieces = [
        (word.speaker or segment.speaker, word.start, word.end)
        if segment.words
        else (segment.speaker, segment.start, segment.end)
        for segment in segments
        if segment.source != NOTE_SOURCE
        for word in (segment.words or (None,))
    ]
    joined: list[tuple[str, float, float]] = []
    for speaker, start, end in sorted(pieces, key=lambda turn: turn[1]):
        if joined and joined[-1][0] == speaker and start - joined[-1][2] < PAUSE_S:
            joined[-1] = (speaker, joined[-1][1], max(joined[-1][2], end))
        else:
            joined.append((speaker, start, end))
    return joined


def speaker_stats(segments: Iterable[Segment]) -> list[SpeakerStats]:
    """Return each speaker's statistics, most talk time first."""
    talk: dict[str, float] = {}
    longest: dict[str, float] = {}
    interruptions: dict[str, int] = {}
    previous: tuple[str, float, float] | None = None
    for speaker, start, end in turns(segments):
        length = max(0.0, end - start)
        talk[speaker] = talk.get(speaker, 0.0) + length
        longest[speaker] = max(longest.get(speaker, 0.0), length)
        interruptions.setdefault(speaker, 0)
        if previous is not None and previous[0] != speaker and start < previous[2] - OVERLAP_S:
            interruptions[speaker] += 1
        if previous is None or end > previous[2]:
            previous = (speaker, start, end)
    total = sum(talk.values()) or 1.0
    return sorted(
        (
            SpeakerStats(speaker, talk[speaker], talk[speaker] / total, longest[speaker], interruptions[speaker])
            for speaker in talk
        ),
        key=lambda stats: -stats.talk_s,
    )


def to_markdown(stats: list[SpeakerStats]) -> str:
    """Render ``stats`` as a ``## Talk time`` Markdown table."""
    rows = [
        f"| {s.speaker} | {clock(s.talk_s)} | {s.share:.0%} | {clock(s.longest_s)} | {s.interruptions} |"
        for s in stats
    ]
    columns = (t("Speaker"), t("Talk time"), t("Share"), t("Longest turn"), t("Interruptions"))
    header = "| " + " | ".join(columns) + " |\n|---|---|---|---|---|"
    return f"## {t('Talk time')}\n\n" + header + "\n" + "\n".join(rows) + "\n"
