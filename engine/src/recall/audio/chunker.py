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
    A long utterance is cut at its quietest block in the last ``lookback_s``
    (usually a breath between words), and the rest starts the next one.
    Speech shorter than ``min_speech_s`` (clicks, coughs) is discarded.

    Not thread-safe: use one instance per audio source.
    """

    # ponytail: per-block RMS, so quiet speech under silence_rms is missed and
    # a monologue with no quieter block in the lookback is still cut at the
    # limit. Whisper's own VAD cleans up inside each utterance; switch to
    # Silero VAD here if boundary errors show up in real meetings.
    def __init__(
        self,
        sample_rate: int,
        *,
        silence_rms: float = 0.01,
        min_silence_s: float = 0.6,
        max_utterance_s: float = 15.0,
        min_speech_s: float = 0.3,
        lookback_s: float = 3.0,
    ) -> None:
        self._rate = sample_rate
        self._silence_rms = silence_rms
        self._min_silence = int(min_silence_s * sample_rate)
        self._max_utterance = int(max_utterance_s * sample_rate)
        self._min_speech = int(min_speech_s * sample_rate)
        self._lookback = int(lookback_s * sample_rate)
        self._position = 0
        self._blocks: list[np.ndarray] = []
        self._levels: list[float] = []
        self._start = 0
        self._speech = 0
        self._trailing_silence = 0

    def feed(self, block: np.ndarray) -> list[Utterance]:
        """Add one block of mono float32 audio; return utterances it completed.

        Usually returns an empty list. Empty blocks are ignored.
        """
        if block.size == 0:
            return []
        level = float(np.sqrt(np.mean(np.square(block))))
        is_speech = level >= self._silence_rms
        block_start = self._position
        self._position += block.size

        if not is_speech and not self._blocks:
            return []
        if not self._blocks:
            self._start = block_start
        self._blocks.append(block)
        self._levels.append(level)
        if is_speech:
            self._speech += block.size
            self._trailing_silence = 0
        else:
            self._trailing_silence += block.size

        buffered = self._position - self._start
        if self._trailing_silence >= self._min_silence:
            return self._flush(len(self._blocks))
        if buffered >= self._max_utterance:
            return self._flush(self._quietest_cut())
        return []

    def _quietest_cut(self) -> int:
        """How many blocks to emit so the cut falls after the quietest recent block.

        Among the blocks in the last ``lookback_s``, the latest of the quietest
        wins, so steady speech is still cut at the limit.
        """
        first = len(self._blocks) - 1
        length = self._blocks[first].size
        while first > 0 and length < self._lookback:
            first -= 1
            length += self._blocks[first].size
        quietest = min(range(first, len(self._blocks)), key=lambda index: (self._levels[index], -index))
        return quietest + 1

    def _flush(self, count: int) -> list[Utterance]:
        """Emit the first ``count`` buffered blocks if they hold enough speech; keep the rest."""
        emitted, kept = self._blocks[:count], self._blocks[count:]
        levels = self._levels[count:]
        utterance = Utterance(self._start / self._rate, np.concatenate(emitted))
        speech = sum(block.size for block, level in zip(emitted, self._levels, strict=False) if level >= self._silence_rms)
        self._start += sum(block.size for block in emitted)
        self._blocks, self._levels = kept, levels
        self._speech = sum(block.size for block, level in zip(kept, levels, strict=True) if level >= self._silence_rms)
        self._trailing_silence = 0
        return [utterance] if speech >= self._min_speech else []
