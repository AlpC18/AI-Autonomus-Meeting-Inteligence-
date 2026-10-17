# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Captures the default microphone as 16 kHz mono blocks."""

import logging
from collections.abc import AsyncIterator

import numpy as np
import sounddevice as sd

from recall.audio.blocks import SAMPLE_RATE, BlockQueue

logger = logging.getLogger(__name__)

_BLOCK_SAMPLES = SAMPLE_RATE // 10


async def microphone_blocks() -> AsyncIterator[np.ndarray]:
    """Yield 100 ms mono float32 blocks from the default input device.

    Runs until the consumer stops iterating, then closes the device. The OS
    asks the user for microphone permission the first time.

    Raises:
        sounddevice.PortAudioError: if there is no input device or it cannot
            be opened (for example, permission was denied).
    """
    queue = BlockQueue("Microphone")

    def on_audio(indata: np.ndarray, _frames: int, _time: object, status: sd.CallbackFlags) -> None:
        if status:
            logger.warning("Microphone stream reported: %s", status)
        queue.put_threadsafe(indata[:, 0].copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=_BLOCK_SAMPLES,
        callback=on_audio,
    ):
        async for block in queue:
            yield block
