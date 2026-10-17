# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Transcript WebSocket: allowed clients receive segments, other origins are refused."""

import json

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from recall.factcheck.checker import FactCheckAlert
from recall.transcript import Segment, Word
from recall.transport.server import TranscriptServer

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
    async with (
        TranscriptServer(port=0, allowed_origins=[ORIGIN]) as server,
        connect(f"ws://127.0.0.1:{server.port}", origin=ORIGIN) as client,
    ):
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


async def test_connected_client_receives_fact_check_alert() -> None:
    from datetime import UTC, datetime

    alert = FactCheckAlert(
        statement="the budget was $50k",
        speaker="others",
        claimed=("$50k",),
        recorded=("$35,000",),
        record_text="the budget was revised down to $35,000",
        record_speaker="SPEAKER_01",
        record_spoken_at=datetime(2026, 8, 14, 10, 0, tzinfo=UTC),
        record_meeting_id="meeting-1",
    )
    async with (
        TranscriptServer(port=0, allowed_origins=[ORIGIN]) as server,
        connect(f"ws://127.0.0.1:{server.port}", origin=ORIGIN) as client,
    ):
        await server.wait_for_clients(1)
        server.publish_alert(alert)
        message = json.loads(await client.recv())

    assert message["type"] == "fact_check"
    assert message["alert"]["claimed"] == ["$50k"]
    assert message["alert"]["recorded"] == ["$35,000"]
    assert message["alert"]["record_spoken_at"] == "2026-08-14T10:00:00+00:00"
