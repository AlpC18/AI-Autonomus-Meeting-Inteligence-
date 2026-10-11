# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Transcript WebSocket: allowed clients receive segments, other origins are refused."""

import json

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from continuum.transcript import Segment, Word
from continuum.transport.server import TranscriptServer

ORIGIN = "http://localhost:1420"
SEGMENT = Segment(
    source="mic",
    start=1.0,
    end=1.5,
    text="hello",
    words=(Word("hello", 1.0, 1.5, "me"),),
    speaker="me",
)


async def test_connected_client_receives_published_segment() -> None:
    async with TranscriptServer(port=0, allowed_origins=[ORIGIN]) as server:
        async with connect(f"ws://127.0.0.1:{server.port}", origin=ORIGIN) as client:
            await server.wait_for_clients(1)
            server.publish(SEGMENT)
            message = json.loads(await client.recv())

    assert message["type"] == "segment"
    assert message["segment"]["text"] == "hello"
    assert message["segment"]["speaker"] == "me"
    assert message["segment"]["words"][0] == {
        "text": "hello",
        "start": 1.0,
        "end": 1.5,
        "speaker": "me",
    }


async def test_connection_from_unlisted_origin_is_refused() -> None:
    async with TranscriptServer(port=0, allowed_origins=[ORIGIN]) as server:
        with pytest.raises(InvalidStatus):
            async with connect(
                f"ws://127.0.0.1:{server.port}", origin="https://evil.example"
            ):
                pass


async def test_publish_without_clients_does_not_fail() -> None:
    async with TranscriptServer(port=0, allowed_origins=[ORIGIN]) as server:
        server.publish(SEGMENT)
