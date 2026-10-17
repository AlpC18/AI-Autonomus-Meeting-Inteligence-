# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The meeting timeline: one entry per stretch of conversation, and one for the last stretch."""

import asyncio
from pathlib import Path

from test_session import NOW, Clock, make, said

from recall.session import MeetingSession
from recall.timeline import TOPIC_WINDOW_S


async def settle(session: MeetingSession) -> None:
    for task in list(session._topics):
        await task
    await asyncio.sleep(0)


async def test_each_stretch_of_conversation_becomes_a_timeline_entry(tmp_path: Path) -> None:
    clock = Clock()
    session, _published, events = await make(tmp_path, clock=clock)

    session.publish(said("Budget is 35,000"))
    clock.now += 30
    session.publish(said("and the launch is in October", start=31.0))
    await settle(session)
    assert [e for e in events if e["type"] == "topic"] == []  # still the first stretch

    clock.now += TOPIC_WINDOW_S
    session.publish(said("Now the hiring plan", start=160.0))
    await settle(session)
    topics = [e for e in events if e["type"] == "topic"]
    assert topics == [{"type": "topic", "at": NOW.isoformat(), "title": "Budget is 35,000"}]

    await session.end()
    await settle(session)
    assert [e["title"] for e in events if e["type"] == "topic"] == ["Budget is 35,000", "Now the hiring plan"]
    kinds = [e["type"] for e in events]
    last_topic = max(index for index, kind in enumerate(kinds) if kind == "topic")
    assert last_topic < kinds.index("meeting_ended")  # never lands in the next meeting's timeline
