# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Splits a continuous audio stream into utterances worth transcribing."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class Utterance:
    """A stretch of speech cut from the stream.

    ``start_s`` is its position on the stream timeline; ``samples`` is mono
    float32 audio at the chunker's sample rate.
    """

    start_s: float
    samples: np.ndarray


class UtteranceChunker:
    """Groups incoming audio blocks into utterances, split at pauses.

    Feed blocks in order with :meth:`feed`. An utterance is emitted when the
    speaker pauses for ``min_silence_s`` or when it reaches
    ``max_utterance_s``, so latency stays bounded during long monologues.
    Speech shorter than ``min_speech_s`` (clicks, coughs) is discarded.

    Not thread-safe: use one instance per audio source.
    """

    # ponytail: per-block RMS threshold, so a cut can land mid-word at
    # max_utterance_s and quiet speech under silence_rms is missed. Whisper's
    # own VAD cleans up inside each utterance; switch to Silero VAD here if
    # boundary errors show up in real meetings.
    def __init__(
        self,
        sample_rate: int,
        *,
        silence_rms: float = 0.01,
        min_silence_s: float = 0.6,
        max_utterance_s: float = 15.0,
        min_speech_s: float = 0.3,
    ) -> None:
        self._rate = sample_rate
        self._silence_rms = silence_rms
        self._min_silence = int(min_silence_s * sample_rate)
        self._max_utterance = int(max_utterance_s * sample_rate)
        self._min_speech = int(min_speech_s * sample_rate)
        self._position = 0
        self._blocks: list[np.ndarray] = []
        self._start = 0
        self._speech = 0
        self._trailing_silence = 0

    def feed(self, block: np.ndarray) -> list[Utterance]:
        """Add one block of mono float32 audio; return utterances it completed.

        Usually returns an empty list. Empty blocks are ignored.
        """
        if block.size == 0:
            return []
        is_speech = float(np.sqrt(np.mean(np.square(block)))) >= self._silence_rms
        block_start = self._position
        self._position += block.size

        if not is_speech and not self._blocks:
            return []
        if not self._blocks:
            self._start = block_start
        self._blocks.append(block)
        if is_speech:
            self._speech += block.size
            self._trailing_silence = 0
        else:
            self._trailing_silence += block.size

        buffered = self._position - self._start
        if self._trailing_silence >= self._min_silence or buffered >= self._max_utterance:
            return self._flush()
        return []

    def _flush(self) -> list[Utterance]:
        """Emit the buffered audio if it holds enough speech, then reset."""
        utterance = Utterance(self._start / self._rate, np.concatenate(self._blocks))
        enough_speech = self._speech >= self._min_speech
        self._blocks = []
        self._speech = 0
        self._trailing_silence = 0
        return [utterance] if enough_speech else []
