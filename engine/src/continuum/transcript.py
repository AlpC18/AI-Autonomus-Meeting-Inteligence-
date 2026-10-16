# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Transcript data shared by the audio, diarization, and transport modules.

All times are seconds since the engine started capturing, so segments from the
microphone and from system audio share one timeline.
"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Word:
    """One transcribed word with its timing and, once known, its speaker."""

    text: str
    start: float
    end: float
    speaker: str | None = None


@dataclass(frozen=True, slots=True)
class Segment:
    """A run of speech transcribed from one audio source.

    ``source`` is the capture stream it came from (``"mic"``, ``"system"`` or ``"tab"``, a browser tab).
    ``speaker`` is the dominant speaker; individual words may differ when
    several people talk within one segment.
    """

    source: str
    start: float
    end: float
    text: str
    words: tuple[Word, ...]
    speaker: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy, used as the wire format."""
        return asdict(self)
