# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Cloud live captions: meeting languages, plausibility, and the local fallback."""

import httpx
import numpy as np
import pytest

from recall.audio.chunker import Utterance
from recall.audio.cloud_transcriber import CloudTranscriber
from recall.transcript import Segment

UTTERANCE = Utterance(10.0, np.zeros(16_000, dtype=np.float32))


def part(text: str, start: float = 0.0, end: float = 1.0, logprob: float = -0.2) -> dict:
    return {"start": start, "end": end, "text": text, "avg_logprob": logprob, "compression_ratio": 1.2, "no_speech_prob": 0.01}


def groq(replies: list[dict], seen: list[dict]) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("latin-1")
        seen.append({"auth": request.headers["Authorization"], "language": "sq" if 'name="language"\r\n\r\nsq' in body else None})
        return httpx.Response(200, json=replies.pop(0))

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_speech_comes_back_on_the_stream_timeline_and_invented_text_is_dropped() -> None:
    seen: list[dict] = []
    reply = {"language": "albanian", "segments": [part("Na duhen dy zhvillues për tre javë.", 0.2, 2.5), part("Thank you for watching!", 2.6, 3.0)]}
    cloud = CloudTranscriber("key", ("sq", "tr"), client=groq([reply], seen))

    segments = cloud.transcribe(UTTERANCE, "system")

    assert [(s.text, s.start, s.speaker) for s in segments] == [("Na duhen dy zhvillues për tre javë.", 10.2, "others")]
    assert seen == [{"auth": "Bearer key", "language": None}]


def test_a_language_not_spoken_here_is_read_again_in_the_meeting_s() -> None:
    seen: list[dict] = []
    replies = [{"language": "russian", "segments": [part("бюджет и увольна")]}, {"language": "albanian", "segments": [part("Buxheti u ul.")]}]
    cloud = CloudTranscriber("key", ("sq", "tr"), client=groq(replies, seen))

    assert [s.text for s in cloud.transcribe(UTTERANCE, "system")] == ["Buxheti u ul."]
    assert [request["language"] for request in seen] == [None, "sq"]


def test_when_groq_fails_the_utterance_is_transcribed_locally() -> None:
    class Local:
        def transcribe(self, utterance: Utterance, source: str) -> list[Segment]:
            return [Segment(source, utterance.start_s, utterance.start_s + 1, "local", (), "me")]

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no internet", request=request)

    cloud = CloudTranscriber("key", (), fallback=Local, client=httpx.Client(transport=httpx.MockTransport(down)))

    assert [s.text for s in cloud.transcribe(UTTERANCE, "mic")] == ["local"]


def test_a_key_is_required() -> None:
    with pytest.raises(ValueError, match="Groq key"):
        CloudTranscriber("")
