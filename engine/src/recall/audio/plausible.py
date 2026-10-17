# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Whether text from the speech model was really said, and in which of the meeting's languages.

Whisper invents text: in silence or noise it writes phrases it learned from
subtitled videos ("Thank you for watching", "Untertitel der
Amara.org-Community"), falls into loops ("nene nene nene"), and on short
speech in a less common language picks the wrong language and writes
nonsense in another alphabet. Live captions and the after-meeting transcript
both pass their text through here.
"""

import re
import unicodedata
import zlib
from collections.abc import Mapping, Sequence

MAX_COMPRESSION_RATIO = 2.4
"""Whisper's own limit: text that compresses better than this is a repetition loop."""

MIN_AVG_LOGPROB = -1.0
"""Whisper's own limit for a decoding it should not trust (used with silence and for the redo)."""

LIVE_MIN_AVG_LOGPROB = -1.5
"""Live captions use the small model, which is less sure even of real speech: only drop the very unsure."""

MAX_NO_SPEECH_PROB = 0.6
"""With a low log probability, this likely means silence or noise was 'transcribed'."""

PHANTOM_PHRASES = (
    "thank you for watching", "thanks for watching", "please subscribe", "subscribe to",
    "like and subscribe", "subtitles by", "amara.org", "transcribed by", "captions by",
    "altyazı m.k.", "izlediğiniz için teşekkürler", "abone olmayı unutmayın",
    "bu dizinin betimlemesi trt tarafından sesli betimleme derneğine yaptırılmıştır",
    "sesli betimleme derneği", "mesetsizlemedernegi",
    "untertitel im auftrag des zdf", "untertitel der amara", "vielen dank fürs zuschauen",
    "sottotitoli creati dalla comunità", "sottotitoli a cura di", "grazie per la visione",
    "faleminderit që na ndoqët", "продолжение следует", "редактор субтитров", "субтитры",
    "ご視聴ありがとうございました", "字幕", "구독과 좋아요",
)  # fmt: skip
"""Phrases Whisper writes for silence or music, learned from subtitled videos."""


def compression_ratio(text: str) -> float:
    """How well ``text`` compresses: "nene nene nene ..." very well."""
    data = text.encode("utf-8")
    return len(data) / len(zlib.compress(data)) if data else 0.0


def _normal(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[\s\W_]+", " ", folded).strip()


def phantom(text: str) -> bool:
    """Whether ``text`` is essentially one of :data:`PHANTOM_PHRASES`."""
    normal = _normal(text)
    for phrase in PHANTOM_PHRASES:
        known = _normal(phrase)
        # The phrase is (nearly) the whole line, not a passing mention in real speech.
        if known and known in normal and len(normal) <= len(known) * 1.6 + 10:
            return True
    return False


def plausible(
    text: str,
    avg_logprob: float,
    reported_compression_ratio: float,
    no_speech_prob: float,
    min_avg_logprob: float = LIVE_MIN_AVG_LOGPROB,
) -> bool:
    """Whether one decoded line looks like something that was really said."""
    if not text.strip() or phantom(text):
        return False
    if no_speech_prob > MAX_NO_SPEECH_PROB and avg_logprob < MIN_AVG_LOGPROB:
        return False  # Whisper's own rule for silence
    if max(reported_compression_ratio, compression_ratio(text)) > MAX_COMPRESSION_RATIO:
        return False
    return avg_logprob >= min_avg_logprob


def most_likely(probabilities: Mapping[str, float], languages: Sequence[str]) -> str | None:
    """The most likely of the meeting's ``languages``, or ``None`` to let the model decide."""
    if not languages:
        return None
    return max(languages, key=lambda language: probabilities.get(language, 0.0))
