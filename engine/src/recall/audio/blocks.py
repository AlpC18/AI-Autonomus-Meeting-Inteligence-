# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Hands audio blocks from an OS capture thread to the asyncio pipeline."""

import asyncio
import logging
from collections.abc import AsyncIterator

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
"""Sample rate, in Hz, of every block in the engine (what Whisper expects)."""


class BlockQueue:
    """A bounded queue that capture callbacks fill and the pipeline drains.

    Create it inside the running event loop. Capture threads call
    :meth:`put_threadsafe`; the pipeline iterates with ``async for``.

    When the pipeline falls behind and the queue is full, new blocks are
    dropped (and a warning logged) rather than growing memory without limit or
    blocking the OS audio thread.
    """

    def __init__(self, name: str, max_blocks: int = 600) -> None:
        self._name = name
        self._loop = asyncio.get_running_loop()
        self._queue: asyncio.Queue[np.ndarray | BaseException] = asyncio.Queue(max_blocks)
        self._dropped = 0

    def put_threadsafe(self, block: np.ndarray) -> None:
        """Queue one mono float32 block. Safe to call from any thread."""
        self._loop.call_soon_threadsafe(self._put, block)

    def fail_threadsafe(self, error: BaseException) -> None:
        """End iteration by raising ``error`` in the consumer. Any thread."""
        self._loop.call_soon_threadsafe(self._put, error)

    def _put(self, item: np.ndarray | BaseException) -> None:
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            self._dropped += 1
            if self._dropped == 1 or self._dropped % 100 == 0:
                logger.warning(
                    "%s audio is arriving faster than it is transcribed; "
                    "%d blocks dropped so far",
                    self._name,
                    self._dropped,
                )

    async def __aiter__(self) -> AsyncIterator[np.ndarray]:
        while True:
            item = await self._queue.get()
            if isinstance(item, BaseException):
                raise item
            yield item
