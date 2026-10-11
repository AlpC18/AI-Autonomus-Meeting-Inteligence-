# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Turns utterances into timestamped transcript segments with faster-whisper."""

from pathlib import Path

from faster_whisper import WhisperModel

from continuum.audio.chunker import Utterance
from continuum.diarization.turns import default_speaker
from continuum.transcript import Segment, Word


class Transcriber:
    """Speech-to-text with word-level timestamps.

    Loading the model is slow and, on first use, downloads it into
    ``model_dir`` (or the Hugging Face cache when ``None``), so create one
    instance and reuse it. :meth:`transcribe` blocks while it computes; call
    it from a worker thread, one call at a time.
    """

    def __init__(self, model_size: str = "base", model_dir: Path | None = None) -> None:
        self._model = WhisperModel(
            model_size,
            device="auto",
            compute_type="default",
            download_root=str(model_dir) if model_dir else None,
        )

    def transcribe(self, utterance: Utterance, source: str) -> list[Segment]:
        """Transcribe one utterance captured from ``source``.

        Times in the result are on the stream timeline (the utterance's start
        is added). Every segment and word is labelled with the speaker implied
        by ``source``; diarization may refine that afterwards. Returns an
        empty list when no speech is recognised.
        """
        raw_segments, _info = self._model.transcribe(
            utterance.samples, word_timestamps=True, vad_filter=True
        )
        speaker = default_speaker(source)
        offset = utterance.start_s
        segments = []
        for raw in raw_segments:
            text = raw.text.strip()
            if not text:
                continue
            words = tuple(
                Word(word.word.strip(), offset + word.start, offset + word.end, speaker)
                for word in raw.words or ()
            )
            segments.append(
                Segment(source, offset + raw.start, offset + raw.end, text, words, speaker)
            )
        return segments
