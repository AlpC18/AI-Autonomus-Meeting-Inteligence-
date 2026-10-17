# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Captures what the speakers play (the other participants) on Windows and Linux.

Uses the ``soundcard`` library: WASAPI loopback on Windows, the speakers'
"monitor" source on Linux (PulseAudio or PipeWire). macOS uses
:mod:`recall.audio.system_audio` (ScreenCaptureKit) instead.
"""

import logging
import threading
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from recall.audio.blocks import SAMPLE_RATE, BlockQueue

logger = logging.getLogger(__name__)

_BLOCK_SAMPLES = SAMPLE_RATE // 10


def _loopback_device(soundcard: Any) -> Any:
    """The loopback recorder of the default speakers.

    Raises:
        RuntimeError: if there are no speakers or no loopback for them.
    """
    speaker = soundcard.default_speaker()
    if speaker is None:
        raise RuntimeError("No speakers were found, so there is no system audio to capture.")
    try:
        return soundcard.get_microphone(id=str(speaker.name), include_loopback=True)
    except (IndexError, ValueError) as error:
        raise RuntimeError(
            f"System audio of {speaker.name!r} cannot be captured on this system."
        ) from error


async def loopback_blocks(soundcard: Any = None) -> AsyncIterator[np.ndarray]:
    """Yield 100 ms mono float32 blocks of what the default speakers play.

    Runs until the consumer stops iterating. ``soundcard`` is the library
    module (injected in tests).

    Raises:
        RuntimeError: if ``soundcard`` is not installed or no loopback device exists.
    """
    if soundcard is None:
        try:
            import soundcard
        except ImportError as error:
            raise RuntimeError(
                "System audio on this platform needs the 'soundcard' package."
            ) from error
    device = _loopback_device(soundcard)
    queue = BlockQueue("System audio")
    stopped = threading.Event()

    def capture() -> None:
        try:
            with device.recorder(samplerate=SAMPLE_RATE, blocksize=_BLOCK_SAMPLES) as recorder:
                while not stopped.is_set():
                    frames = np.asarray(recorder.record(numframes=_BLOCK_SAMPLES), dtype=np.float32)
                    mono = frames.mean(axis=1) if frames.ndim == 2 else frames
                    queue.put_threadsafe(mono.astype(np.float32))
        except Exception as error:  # noqa: BLE001 - any capture failure ends this source
            queue.fail_threadsafe(error)

    thread = threading.Thread(target=capture, name="loopback-capture", daemon=True)
    thread.start()
    try:
        async for block in queue:
            yield block
    finally:
        stopped.set()
