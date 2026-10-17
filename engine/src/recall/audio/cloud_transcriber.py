# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Live captions from Groq's Whisper large-v3-turbo, for languages the local models cannot keep up with.

Opt-in (``RECALL_ASR_BACKEND=groq``): each utterance's audio is sent to Groq.
On an M1 the local models that keep up live write Albanian as nonsense or in
Cyrillic, while large-v3-turbo understands it but needs 5-7 s per sentence;
Groq runs that model in about a second. The meeting languages and the
plausibility checks apply as for local models, and if Groq cannot be reached
the utterance is transcribed locally instead, so nothing said is lost.
"""

import io
import logging
import wave
from collections.abc import Callable, Sequence

import httpx
import numpy as np

from recall.audio.blocks import SAMPLE_RATE
from recall.audio.chunker import Utterance
from recall.audio.plausible import plausible
from recall.transcript import Segment

logger = logging.getLogger(__name__)

URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3-turbo"
TIMEOUT_S = 15.0

# Groq names the detected language in English; the meeting languages are codes.
_NAMES = {
    "english": "en", "turkish": "tr", "german": "de", "italian": "it", "albanian": "sq",
    "french": "fr", "spanish": "es", "portuguese": "pt", "dutch": "nl", "polish": "pl",
    "russian": "ru", "arabic": "ar", "greek": "el", "bosnian": "bs", "serbian": "sr",
}  # fmt: skip


def _wav(samples: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes((np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes())
    return buffer.getvalue()


def _code(language: str | None) -> str | None:
    if not language:
        return None
    lowered = language.strip().lower()
    return _NAMES.get(lowered, lowered)


class CloudTranscriber:
    """Same contract as :class:`recall.audio.transcriber.Transcriber`, through Groq's API.

    ``fallback`` makes the local model on first need, for when Groq fails.
    """

    def __init__(
        self,
        api_key: str,
        languages: Sequence[str] = (),
        fallback: Callable[[], object] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Cloud speech needs a Groq key: set GROQ_API_KEY in Settings.")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._languages = tuple(languages)
        self._client = client or httpx.Client(timeout=TIMEOUT_S)
        self._make_fallback = fallback
        self._fallback = None
        # The language of the last utterance in a meeting language: people seldom switch mid-flow.
        self._last_language = self._languages[0] if self._languages else None

    def transcribe(self, utterance: Utterance, source: str):
        """Transcribe one utterance (see :meth:`Transcriber.transcribe`)."""
        try:
            return self._cloud(utterance, source)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            logger.warning("Cloud speech failed (%s); transcribing this utterance locally", error)
            if self._make_fallback is None:
                return []
            if self._fallback is None:
                self._fallback = self._make_fallback()
            return self._fallback.transcribe(utterance, source)  # type: ignore[attr-defined]

    def _cloud(self, utterance: Utterance, source: str) -> list[Segment]:
        forced = self._languages[0] if len(self._languages) == 1 else None
        reply = self._request(utterance.samples, forced)
        detected = _code(reply.get("language"))
        if self._languages and detected not in self._languages:
            # Heard as a language not spoken here (Albanian as Russian): read it in the meeting's.
            reply = self._request(utterance.samples, self._last_language)
            detected = self._last_language
        if detected in self._languages:
            self._last_language = detected
        return self._segments(reply, utterance, source)

    def _request(self, samples: np.ndarray, language: str | None) -> dict:
        data = {"model": MODEL, "response_format": "verbose_json", "temperature": "0"}
        if language:
            data["language"] = language
        response = self._client.post(
            URL,
            headers=self._headers,
            data=data,
            files={"file": ("utterance.wav", _wav(samples), "audio/wav")},
        )
        response.raise_for_status()
        reply = response.json()
        if not isinstance(reply, dict):
            raise TypeError("unexpected reply from Groq")
        return reply

    @staticmethod
    def _segments(reply: dict, utterance: Utterance, source: str) -> list[Segment]:
        from recall.diarization.turns import default_speaker

        speaker = default_speaker(source)
        offset = utterance.start_s
        found = []
        for part in reply.get("segments", []):
            text = str(part.get("text", "")).strip()
            if not plausible(
                text,
                float(part.get("avg_logprob", 0.0)),
                float(part.get("compression_ratio", 0.0)),
                float(part.get("no_speech_prob", 0.0)),
            ):
                continue
            found.append(Segment(source, offset + float(part["start"]), offset + float(part["end"]), text, (), speaker))
        return found
