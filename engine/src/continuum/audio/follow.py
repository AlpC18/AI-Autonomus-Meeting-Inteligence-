# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Following the meeting app's audio as apps open and close (Windows and Linux)."""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from continuum.audio.blocks import SAMPLE_RATE, BlockQueue

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class Process:
    """A running app to hear: its process (or, on Linux, audio stream) id, parent, and name."""

    pid: int
    parent: int
    name: str


APP_REFRESH_S = 10.0
_BLOCK = SAMPLE_RATE // 10
_POLL_S = 0.01


def follow_app(
    queue: BlockQueue,
    stopped: threading.Event,
    choose: Callable[[], Process | None],
    open_capture: Callable[[int], Any],
    enter: Callable[[], Callable[[], None]] = lambda: lambda: None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Capture loop for a worker thread: follow the meeting app, emit 100 ms blocks.

    ``choose`` names the app to hear now (re-asked every :data:`APP_REFRESH_S`);
    ``open_capture(pid)`` returns something with ``read()`` (float32 samples
    available now) and ``close()``. ``enter`` sets up the thread (COM on
    Windows) and returns how to tear it down.
    """
    leave = enter()
    capture, heard, pending = None, None, np.zeros(0, dtype=np.float32)
    next_check = 0.0
    last = clock()
    try:
        while not stopped.is_set():
            now = clock()
            if now >= next_check:
                next_check = now + APP_REFRESH_S
                chosen = choose()
                if (chosen.pid if chosen else None) != heard:
                    if capture is not None:
                        capture.close()
                    capture = open_capture(chosen.pid) if chosen else None
                    heard = chosen.pid if chosen else None
                    logger.info("Hearing %s", chosen.name if chosen else "no meeting app (none running)")
            samples = capture.read() if capture is not None else np.zeros(0, np.float32)
            if samples.size == 0:
                # Nothing is played (or no meeting app runs): silence keeps the
                # chunker's clock moving, so the last utterance still ends.
                samples = np.zeros(int((now - last) * SAMPLE_RATE), np.float32)
            last = now
            pending = np.concatenate([pending, samples])
            while pending.size >= _BLOCK:
                queue.put_threadsafe(pending[:_BLOCK].copy())
                pending = pending[_BLOCK:]
            sleep(_POLL_S)
    except Exception as error:  # noqa: BLE001 - any capture failure ends this source
        queue.fail_threadsafe(error)
    finally:
        if capture is not None:
            capture.close()
        leave()


