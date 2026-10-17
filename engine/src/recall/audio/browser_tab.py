# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Audio of one browser tab (Google Meet, Teams or Zoom on the web), sent by the extension.

macOS captures audio per app, so with a call in a browser every other tab
would be heard too. The Recall browser extension (``apps/browser-extension``)
captures only the tab the user chose and streams it here: binary WebSocket
messages of 16 kHz mono float32 samples, little-endian.

The server listens on the loopback interface only and accepts connections
only from a Chrome or Firefox extension origin (or exactly the configured extension),
so a web page cannot send audio. One tab at a time: a second connection is
refused while one is open, because two tabs would interleave in one transcript.
"""

import asyncio
import logging
import re
from collections.abc import AsyncIterator

import numpy as np
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.typing import Origin

logger = logging.getLogger(__name__)

TAB_PORT = 8766
"""Port the extension connects to (``ws://127.0.0.1:8766``)."""

EXTENSION_ID = re.compile(r"[a-p]{32}")
"""Shape of a Chrome extension ID."""

FIREFOX_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
"""Shape of a Firefox extension's internal UUID (about:debugging shows it)."""

MAX_MESSAGE = 64 * 1024
"""Largest audio message accepted (about 1 s); the extension sends 100 ms."""

_QUEUE_BLOCKS = 600


def _origins(extension_id: str | None) -> list[Origin | re.Pattern[str]]:
    if extension_id is not None:
        if EXTENSION_ID.fullmatch(extension_id):
            return [Origin(f"chrome-extension://{extension_id}")]
        if FIREFOX_ID.fullmatch(extension_id):
            return [Origin(f"moz-extension://{extension_id}")]
        raise ValueError(f"not a Chrome or Firefox extension ID: {extension_id!r}")
    return [re.compile(rf"chrome-extension://{EXTENSION_ID.pattern}"), re.compile(rf"moz-extension://{FIREFOX_ID.pattern}")]


def to_block(message: bytes | str) -> np.ndarray | None:
    """The samples in one message, clipped to [-1, 1]; ``None`` if it is not audio."""
    if isinstance(message, str) or not message or len(message) % 4:
        return None
    samples = np.frombuffer(message, dtype="<f4")
    return np.clip(np.nan_to_num(samples, nan=0.0, posinf=1.0, neginf=-1.0), -1.0, 1.0).astype(np.float32)


async def tab_audio_blocks(
    port: int = TAB_PORT, extension_id: str | None = None, host: str = "127.0.0.1"
) -> AsyncIterator[np.ndarray]:
    """Yield blocks of the captured tab's audio; waits while no tab is captured.

    Runs until the consumer stops iterating.

    Raises:
        ValueError: if ``extension_id`` is not a Chrome extension ID.
        OSError: if the port is taken.
    """
    queue: asyncio.Queue[np.ndarray] = asyncio.Queue(_QUEUE_BLOCKS)
    busy = asyncio.Lock()

    async def receive(connection: ServerConnection) -> None:
        if busy.locked():
            await connection.close(1008, "Another tab is already being captured.")
            return
        async with busy:
            logger.info("Browser tab audio connected")
            try:
                async for message in connection:
                    block = to_block(message)
                    if block is None:
                        continue
                    try:
                        queue.put_nowait(block)
                    except asyncio.QueueFull:
                        pass  # transcription is behind; drop rather than grow without limit
            except ConnectionClosed:
                pass
            logger.info("Browser tab audio disconnected")

    async with serve(receive, host, port, origins=_origins(extension_id), max_size=MAX_MESSAGE):
        logger.info("Waiting for browser tab audio on ws://%s:%d", host, port)
        while True:
            yield await queue.get()
