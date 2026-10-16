# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Local WebSocket server that streams live transcript segments to the HUD."""

import asyncio
import json
import logging
from collections.abc import Sequence
from types import TracebackType
from typing import Self

from websockets.asyncio.server import Server, ServerConnection, broadcast, serve
from websockets.typing import Origin

from continuum.factcheck.checker import FactCheckAlert
from continuum.transcript import Segment

logger = logging.getLogger(__name__)

DESKTOP_ORIGINS: tuple[str, ...] = (
    "tauri://localhost",
    "http://tauri.localhost",
    "http://localhost:1420",
)
"""Origins of the Tauri webview: macOS/Linux, Windows, and the Vite dev server."""


class TranscriptServer:
    """Broadcasts transcript segments to every connected desktop client.

    Use as an async context manager. The server listens on the loopback
    interface only, and refuses connections whose ``Origin`` header is not in
    ``allowed_origins``: transcripts are private, and without that check any
    web page open in a browser could connect and read them.

    Messages are JSON, either ``{"type": "segment", "segment": {...}}`` or
    ``{"type": "fact_check", "alert": {...}}``. Clients that connect late
    receive only what is published after they joined.
    """

    def __init__(
        self,
        *,
        port: int,
        host: str = "127.0.0.1",
        allowed_origins: Sequence[str] = DESKTOP_ORIGINS,
    ) -> None:
        self._host = host
        self._requested_port = port
        self._origins = [Origin(origin) for origin in allowed_origins]
        self._clients: set[ServerConnection] = set()
        self._client_joined = asyncio.Condition()
        self._server: Server | None = None

    @property
    def port(self) -> int:
        """The port actually bound (useful when constructed with ``port=0``).

        Raises:
            RuntimeError: if the server has not been started.
        """
        if self._server is None:
            raise RuntimeError("TranscriptServer is not running")
        return next(iter(self._server.sockets)).getsockname()[1]

    async def __aenter__(self) -> Self:
        self._server = await serve(
            self._handle, self._host, self._requested_port, origins=self._origins
        )
        logger.info("Transcript stream listening on ws://%s:%d", self._host, self.port)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def publish(self, segment: Segment) -> None:
        """Send ``segment`` to all connected clients without waiting.

        Never raises for client problems: a slow or disconnected client is
        skipped so it cannot stall the audio pipeline.
        """
        message = json.dumps({"type": "segment", "segment": segment.to_dict()})
        broadcast(self._clients, message)

    def publish_alert(self, alert: FactCheckAlert) -> None:
        """Send a fact-check alert to all connected clients without waiting.

        Like :meth:`publish`, it never raises for client problems.
        """
        message = json.dumps({"type": "fact_check", "alert": alert.to_dict()})
        broadcast(self._clients, message)

    async def wait_for_clients(self, count: int) -> None:
        """Block until at least ``count`` clients are connected."""
        async with self._client_joined:
            await self._client_joined.wait_for(lambda: len(self._clients) >= count)

    async def _handle(self, connection: ServerConnection) -> None:
        self._clients.add(connection)
        async with self._client_joined:
            self._client_joined.notify_all()
        try:
            await connection.wait_closed()
        finally:
            self._clients.discard(connection)
