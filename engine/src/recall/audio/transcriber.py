# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Turns utterances into timestamped transcript segments.

Two backends with the same interface: faster-whisper (everywhere) and
mlx-whisper (Apple Silicon GPU, about 3x faster on an M1 for the same model;
installed with the ``apple`` extra).
"""

import importlib.util
import platform
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

from recall.audio.chunker import Utterance
from recall.audio.plausible import most_likely, plausible
from recall.diarization.turns import default_speaker
from recall.transcript import Segment, Word

BACKENDS = ("auto", "faster-whisper", "mlx")
"""Values accepted in ``RECALL_ASR_BACKEND``."""

RawWord = tuple[str, float, float]
RawSegment = tuple[float, float, str, Iterable[RawWord]]


class SpeechToText(Protocol):
    """Anything that transcribes an utterance the way :class:`Transcriber` does."""

    def transcribe(self, utterance: Utterance, source: str) -> list[Segment]:
        """See :meth:`Transcriber.transcribe`."""
        ...


def _segments(raw_segments: Iterable[RawSegment], utterance: Utterance, source: str) -> list[Segment]:
    """Shift model output onto the stream timeline and label it by ``source``."""
    speaker = default_speaker(source)
    offset = utterance.start_s
    segments = []
    for start, end, raw_text, raw_words in raw_segments:
        text = raw_text.strip()
        if not text:
            continue
        words = tuple(
            Word(word.strip(), offset + word_start, offset + word_end, speaker)
            for word, word_start, word_end in raw_words
        )
        segments.append(Segment(source, offset + start, offset + end, text, words, speaker))
    return segments


class Transcriber:
    """Speech-to-text with word-level timestamps, using faster-whisper.

    Loading the model is slow and, on first use, downloads it into
    ``model_dir`` (or the Hugging Face cache when ``None``), so create one
    instance and reuse it. :meth:`transcribe` blocks while it computes; call
    it from a worker thread, one call at a time.
    """

    def __init__(
        self,
        model_size: str = "base",
        model_dir: Path | None = None,
        *,
        translate: bool = False,
        languages: Sequence[str] = (),
    ) -> None:
        """With ``translate`` the output is English whatever language is spoken.

        ``languages`` are the meeting's: speech is only ever written in one of them.
        """
        from faster_whisper import WhisperModel

        self._languages = tuple(languages)
        self._task = "translate" if translate else "transcribe"
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
        language = self._languages[0] if len(self._languages) == 1 else None
        if len(self._languages) > 1:
            _best, _probability, ranked = self._model.detect_language(utterance.samples)
            language = most_likely(dict(ranked), self._languages)
        raw_segments, _info = self._model.transcribe(
            utterance.samples, word_timestamps=True, vad_filter=True, task=self._task, language=language
        )
        return _segments(
            (
                (raw.start, raw.end, raw.text, ((w.word, w.start, w.end) for w in raw.words or ()))
                for raw in raw_segments
                if plausible(raw.text, raw.avg_logprob, raw.compression_ratio, raw.no_speech_prob)
            ),
            utterance,
            source,
        )


def mlx_repo(model_size: str) -> str:
    """Hugging Face repo of the MLX conversion of a Whisper model size.

    ``base`` becomes ``mlx-community/whisper-base-mlx``; turbo models have no
    ``-mlx`` suffix; a value containing ``/`` is already a repo id.
    """
    if "/" in model_size:
        return model_size
    suffix = "" if "turbo" in model_size else "-mlx"
    return f"mlx-community/whisper-{model_size}{suffix}"


class MlxTranscriber:
    """Speech-to-text on the Apple Silicon GPU with mlx-whisper.

    Same contract as :class:`Transcriber`. Utterances arrive already cut at
    pauses, so each is transcribed on its own (no carried-over context,
    which also stops one misheard phrase from repeating).

    Raises:
        RuntimeError: on construction, if mlx-whisper is not installed.
    """

    def __init__(
        self,
        model_size: str = "base",
        model_dir: Path | None = None,
        *,
        translate: bool = False,
        languages: Sequence[str] = (),
    ) -> None:
        if importlib.util.find_spec("mlx_whisper") is None:
            raise RuntimeError(
                "The mlx backend needs mlx-whisper on an Apple Silicon Mac: run `uv sync --extra apple`"
            )
        import mlx_whisper
        from huggingface_hub import snapshot_download

        self._transcribe = mlx_whisper.transcribe
        self._languages = tuple(languages)
        self._task = "translate" if translate else "transcribe"
        # Downloads once into model_dir, like faster-whisper's download_root.
        self._repo = snapshot_download(
            mlx_repo(model_size), cache_dir=str(model_dir) if model_dir else None
        )

    def transcribe(self, utterance: Utterance, source: str) -> list[Segment]:
        """See :meth:`Transcriber.transcribe`."""
        result = self._transcribe(
            utterance.samples,
            path_or_hf_repo=self._repo,
            word_timestamps=True,
            condition_on_previous_text=False,
            task=self._task,
            language=self._language(utterance.samples),
            verbose=None,
        )
        return _segments(
            (
                (
                    raw["start"],
                    raw["end"],
                    raw["text"],
                    ((w["word"], w["start"], w["end"]) for w in raw.get("words", ())),
                )
                for raw in result["segments"]
                if plausible(raw["text"], raw["avg_logprob"], raw["compression_ratio"], raw["no_speech_prob"])
            ),
            utterance,
            source,
        )

    def _language(self, samples) -> str | None:
        """The meeting language this speech is most likely in (``None``: any language)."""
        if len(self._languages) <= 1:
            return self._languages[0] if self._languages else None
        import mlx.core as mx
        from mlx_whisper.audio import log_mel_spectrogram, pad_or_trim
        from mlx_whisper.decoding import detect_language
        from mlx_whisper.transcribe import ModelHolder

        model = ModelHolder.get_model(self._repo, mx.float16)
        mel = log_mel_spectrogram(pad_or_trim(mx.array(samples)), n_mels=model.dims.n_mels)
        _tokens, probabilities = detect_language(model, mel.astype(mx.float16))
        ranked = probabilities if isinstance(probabilities, dict) else probabilities[0]
        return most_likely(ranked, self._languages)


def mlx_available() -> bool:
    """Whether this machine can run the mlx backend (Apple Silicon with the extra installed)."""
    return (
        sys.platform == "darwin"
        and platform.machine() == "arm64"
        and importlib.util.find_spec("mlx_whisper") is not None
    )


def load_transcriber(
    backend: str,
    model_size: str,
    model_dir: Path | None,
    *,
    translate: bool = False,
    languages: Sequence[str] = (),
) -> SpeechToText:
    """Load the speech model for ``backend`` (see :data:`BACKENDS`).

    ``auto`` picks mlx when :func:`mlx_available`, otherwise faster-whisper.

    Raises:
        ValueError: if ``backend`` is unknown.
        RuntimeError: if mlx is requested but cannot run here.
    """
    if backend not in BACKENDS:
        raise ValueError(f"unknown speech backend {backend!r}; use one of {BACKENDS}")
    if backend == "mlx" or (backend == "auto" and mlx_available()):
        return MlxTranscriber(model_size, model_dir, translate=translate, languages=languages)
    return Transcriber(model_size, model_dir, translate=translate, languages=languages)
