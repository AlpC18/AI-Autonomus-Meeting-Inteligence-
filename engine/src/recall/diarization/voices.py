# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Remembers the voices of people the user has named, across meetings.

When the user names "Speaker 2" as "Ayşe", her voice embedding is saved
under that name when the meeting ends; in a later meeting a new speaker
whose voice matches is shown as "Ayşe" straight away. Only voices the user
named are kept, and only on this computer, in one JSON file readable by the
current user only. Deleting the file forgets every voice.
"""

import json
import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

RECOGNISE = 0.6
"""Similarity at which a voice is taken to be someone named before. As strict
as merging duplicate speakers: showing the wrong person's name is worse than
showing "Speaker 3"."""

MAX_NAME = 80


def _unit(voice: np.ndarray) -> np.ndarray | None:
    vector = np.asarray(voice, dtype=np.float64).ravel()
    length = float(np.linalg.norm(vector))
    if not np.isfinite(length) or length == 0.0:
        return None
    return vector / length


class VoiceBook:
    """Named voice embeddings kept in a JSON file.

    Not thread-safe: use it from one thread at a time.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._voices: dict[str, np.ndarray] = {}
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            logger.exception("Could not read remembered voices from %s; starting empty", path)
            return
        if not isinstance(stored, dict):
            return
        for name, values in stored.items():
            if isinstance(name, str) and 0 < len(name) <= MAX_NAME and isinstance(values, list):
                try:
                    unit = _unit(np.array(values, dtype=np.float64))
                except (TypeError, ValueError):
                    continue
                if unit is not None:
                    self._voices[name] = unit

    @property
    def names(self) -> list[str]:
        """Names of everyone whose voice is remembered."""
        return sorted(self._voices)

    def identify(self, voice: np.ndarray, threshold: float = RECOGNISE) -> str | None:
        """The remembered name whose voice best matches ``voice``, if close enough."""
        unit = _unit(voice)
        if unit is None:
            return None
        best, best_score = None, threshold
        for name, known in self._voices.items():
            if known.shape != unit.shape:
                continue
            score = float(unit @ known)
            if score >= best_score:
                best, best_score = name, score
        return best

    def learn(self, name: str, voice: np.ndarray) -> None:
        """Remember ``voice`` as ``name``, blending with what was known, and save.

        Raises:
            OSError: if the file cannot be written.
        """
        unit = _unit(voice)
        if unit is None or not 0 < len(name) <= MAX_NAME:
            return
        known = self._voices.get(name)
        if known is not None and known.shape == unit.shape:
            unit = _unit(known + unit)
            if unit is None:
                return
        self._voices = {**self._voices, name: unit}
        self._save()

    def forget(self, name: str) -> bool:
        """Forget ``name``'s voice; returns whether it was remembered."""
        if name not in self._voices:
            return False
        self._voices = {key: value for key, value in self._voices.items() if key != name}
        self._save()
        return True

    def _save(self) -> None:
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        data = {name: [round(float(x), 6) for x in voice] for name, voice in self._voices.items()}
        # Voices are biometric data: only the current user may read the file.
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(data, file)
        os.replace(temporary, self._path)
