# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Keeps each speaker's name the same for a whole session."""

import numpy as np

MATCH = 0.5
"""Cosine similarity at or above which two voice embeddings are one person.
Measured with the pyannote community-1 embedding model on clean clips of
1.6-6 s: the same person scored 0.58-0.96, different people 0.44 or less."""

MIN_VOICE_S = 1.0
"""Speech shorter than this is too little to learn a voice from."""

MERGE = 0.6
"""Similarity at which two speakers' final voices are taken to be one person.
Stricter than :data:`MATCH`: wrongly merging two people is worse than
leaving one person under two names."""


class SpeakerTracker:
    """Recognises voices heard earlier in the session and names new ones.

    Speakers are called "Speaker 1", "Speaker 2", ... in the order they are
    first heard. Each known speaker is remembered as the average of the voice
    embeddings matched to them so far.

    Not thread-safe: use one instance per audio stream.
    """

    # ponytail: greedy matching against running averages, never revised. Two
    # similar voices can merge and a noisy clip can add a speaker who is not
    # there; re-clustering the whole session at the end would repair both.
    def __init__(self, match: float = MATCH) -> None:
        self._match = match
        self._voices: list[np.ndarray] = []

    def name(self, voice: np.ndarray, seconds: float) -> str | None:
        """Return the session name of the speaker with this voice embedding.

        ``seconds`` is how much speech the embedding was computed from. With
        at least :data:`MIN_VOICE_S` of speech, a voice that matches nobody
        becomes a new speaker. Shorter speech only ever matches a speaker who
        is already known. Returns ``None`` when no name can be given: the
        embedding is unusable, or the speech is short and matches nobody.
        """
        length = float(np.linalg.norm(voice))
        if not np.isfinite(length) or length == 0.0:
            return None
        unit = voice / length
        enough = seconds >= MIN_VOICE_S

        scores = [float(unit @ known) / float(np.linalg.norm(known)) for known in self._voices]
        best = int(np.argmax(scores)) if scores else -1
        if best >= 0 and scores[best] >= self._match:
            if enough:
                self._voices[best] = self._voices[best] + unit
            return f"Speaker {best + 1}"
        if not enough:
            return None
        self._voices.append(unit)
        return f"Speaker {len(self._voices)}"

    def merges(self, threshold: float = MERGE) -> dict[str, str]:
        """Speakers who turned out to be one person: ``{later name: earlier name}``.

        Early in a meeting a voice is matched against little evidence, so one
        person can end up as two speakers. Comparing the final averaged
        voices, which hold much more evidence, finds those duplicates.
        """
        units = [voice / float(np.linalg.norm(voice)) for voice in self._voices]
        result: dict[str, str] = {}
        for later in range(1, len(units)):
            scores = [float(units[later] @ units[earlier]) for earlier in range(later)]
            best = int(np.argmax(scores))
            if scores[best] >= threshold:
                target = f"Speaker {best + 1}"
                result[f"Speaker {later + 1}"] = result.get(target, target)
        return result
