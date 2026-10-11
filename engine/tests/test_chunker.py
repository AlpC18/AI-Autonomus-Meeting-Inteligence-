# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Utterance chunking: speech is grouped, silence splits it, long speech is cut."""

import numpy as np

from continuum.audio.chunker import UtteranceChunker

RATE = 16_000
BLOCK = RATE // 10  # 100 ms


def speech(blocks: int) -> list[np.ndarray]:
    return [np.full(BLOCK, 0.2, dtype=np.float32) for _ in range(blocks)]


def silence(blocks: int) -> list[np.ndarray]:
    return [np.zeros(BLOCK, dtype=np.float32) for _ in range(blocks)]


def feed_all(chunker: UtteranceChunker, blocks: list[np.ndarray]) -> list:
    return [utterance for block in blocks for utterance in chunker.feed(block)]


def test_silence_alone_emits_nothing() -> None:
    assert feed_all(UtteranceChunker(RATE), silence(50)) == []


def test_speech_then_silence_emits_one_utterance_with_its_start_time() -> None:
    chunker = UtteranceChunker(RATE, min_silence_s=0.5)
    utterances = feed_all(chunker, silence(10) + speech(20) + silence(10))

    assert len(utterances) == 1
    assert utterances[0].start_s == 1.0
    assert 2.0 <= len(utterances[0].samples) / RATE <= 2.6


def test_short_pause_does_not_split_an_utterance() -> None:
    chunker = UtteranceChunker(RATE, min_silence_s=0.5)
    utterances = feed_all(chunker, speech(10) + silence(2) + speech(10) + silence(10))

    assert len(utterances) == 1


def test_continuous_speech_is_cut_at_the_maximum_length() -> None:
    chunker = UtteranceChunker(RATE, max_utterance_s=3.0)
    utterances = feed_all(chunker, speech(70))

    assert len(utterances) == 2
    assert utterances[1].start_s == 3.0


def test_blip_shorter_than_minimum_is_dropped() -> None:
    chunker = UtteranceChunker(RATE, min_silence_s=0.5, min_speech_s=0.3)
    assert feed_all(chunker, speech(1) + silence(10)) == []
