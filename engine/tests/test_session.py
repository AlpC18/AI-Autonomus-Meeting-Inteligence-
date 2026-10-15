# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Meeting lifecycle: notes, names, questions, ending with a summary, idle stop, recording."""

import json
import wave
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from continuum.config import Settings
from continuum.live_controls import NOTE_SPEAKER
from continuum.memory.store import MemoryHit
from continuum.session import MeetingSession
from continuum.transcript import Segment, Word

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
SUMMARY = json.dumps(
    {
        "overview": "Budget agreed.",
        "decisions": ["Budget is $35,000"],
        "action_items": [{"task": "Send the report", "owner": "Ana", "due": "2026-11-30"}],
    }
)


def said(text: str, speaker: str = "Speaker 1", start: float = 1.0) -> Segment:
    return Segment("system", start, start + 1, text, (Word(text, start, start + 1, speaker),), speaker)


class FakeMemory:
    def __init__(self) -> None:
        self.stored: list[tuple[Segment, str, bool]] = []
        self.renamed: list[tuple[str, str, str]] = []

    def add_segment(self, segment: Segment, meeting, *, disputed: bool = False) -> None:
        self.stored.append((segment, meeting.meeting_id, disputed))

    def search(self, query: str, limit: int = 5) -> list[MemoryHit]:
        return [MemoryHit("Budget is $35,000", "Ana", "system", "m0", NOW, 0.9, "acme", "web")]

    def rename_speaker(self, meeting_id: str, old: str, new: str) -> None:
        self.renamed.append((meeting_id, old, new))


class FakeLlm:
    def __init__(self, reply: str = SUMMARY) -> None:
        self.reply, self.calls = reply, []

    def complete(self, system: str, user: str) -> str:
        self.calls.append(user)
        return self.reply


class FakeSpeakers:
    def __init__(self, merges: dict[str, str] | None = None, known: dict[str, str] | None = None) -> None:
        self.merges, self.resets = merges or {}, 0
        self.known = known or {}
        self.learned: list[tuple[str, str]] = []

    def recognise(self, label: str) -> str | None:
        return self.known.get(label)

    def learn(self, label: str, name: str) -> None:
        self.learned.append((label, name))

    def speaker_merges(self) -> dict[str, str]:
        return self.merges

    def reset(self) -> None:
        self.resets += 1


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def make(tmp_path: Path, **kwargs) -> tuple[MeetingSession, list[Segment], list[dict]]:
    settings_kwargs = kwargs.pop("settings", {})
    settings = Settings(notes_dir=tmp_path / "notes", **settings_kwargs)
    session = MeetingSession(settings, now=lambda: NOW, **kwargs)
    published: list[Segment] = []
    events: list[dict] = []
    session.connect(published.append, events.append)
    await session.start()
    return session, published, events


async def test_notes_and_renames_reach_transcript_notes_and_memory(tmp_path: Path) -> None:
    memory = FakeMemory()
    session, published, events = await make(tmp_path, memory=memory)

    await session.handle('{"type": "note", "text": "Decision needed on vendor"}')
    await session.handle('{"type": "rename_speaker", "from": "Speaker 2", "to": "Mark"}')
    await session.handle('{"type": "note"}')

    assert [segment.text for segment in published] == ["Decision needed on vendor", "Speaker 2 is now called Mark."]
    assert all(segment.speaker == NOTE_SPEAKER for segment in published)
    assert [disputed for _segment, _meeting, disputed in memory.stored] == [False, False]
    assert {"type": "renamed", "from": "Speaker 2", "to": "Mark"} in events
    assert session.relabel(said("hi", "Speaker 2")).speaker == "Mark"
    assert "**Note:** Decision needed on vendor" in session.notes_path.read_text()


async def test_stored_text_is_redacted_but_the_live_transcript_is_not(tmp_path: Path) -> None:
    memory = FakeMemory()
    session, published, _events = await make(tmp_path, memory=memory)
    segment = said("write to ana@acme.io")

    session.publish(segment)
    session.remember(segment, False)

    assert published[0].text == "write to ana@acme.io"
    assert "[email]" in session.notes_path.read_text() and "ana@acme.io" not in session.notes_path.read_text()
    assert memory.stored[0][0].text == "write to [email]"


async def test_questions_are_answered_from_memory(tmp_path: Path) -> None:
    session, _published, events = await make(tmp_path, memory=FakeMemory(), llm=FakeLlm("It is $35,000 [1]."))

    await session.handle('{"type": "ask", "id": "q1", "question": "What is the budget?"}')

    (reply,) = [event for event in events if event["type"] == "answer"]
    assert reply["id"] == "q1" and reply["text"] == "It is $35,000 [1]."
    assert reply["sources"][0]["number"] == 1


async def test_questions_explain_what_is_missing(tmp_path: Path) -> None:
    session, _published, events = await make(tmp_path)
    await session.handle('{"type": "ask", "id": "q2", "question": "budget?"}')
    assert "Memory is off" in events[-1]["error"]


async def test_ending_a_meeting_summarises_merges_proposes_and_starts_the_next(tmp_path: Path) -> None:
    memory, llm, speakers = FakeMemory(), FakeLlm(), FakeSpeakers({"Speaker 3": "Speaker 1"})
    proposed: list[str] = []

    def propose(summary, source, event):
        proposed.append(summary.action_items[0].task)
        return 1, []

    session, _published, events = await make(
        tmp_path,
        memory=memory,
        llm=llm,
        speakers=speakers,
        propose=propose,
        settings={"auto_propose": ("calendar",)},
    )
    first_meeting, first_notes = session.meeting.meeting_id, session.notes_path
    session.publish(said("Budget is 35k", "Speaker 1"))
    session.publish(said("I agree, ana@acme.io", "Speaker 3", 3.0))

    await session.handle('{"type": "end_meeting"}')

    notes = first_notes.read_text()
    assert "**Speaker 3:**" not in notes and notes.count("**Speaker 1:**") == 2
    assert "## Summary" in notes and "- [ ] Send the report (Ana, due 2026-11-30)" in notes
    assert memory.renamed == [(first_meeting, "Speaker 3", "Speaker 1")]
    assert "ana@acme.io" not in llm.calls[0]  # the provider gets the redacted transcript
    assert proposed == ["Send the report"]
    summary = next(event for event in events if event["type"] == "summary")
    assert summary["queued"] == 1 and summary["markdown"].startswith("## Summary")
    assert speakers.resets == 1
    assert session.meeting.meeting_id != first_meeting
    assert [event["type"] for event in events].count("meeting_started") == 2


async def test_a_meeting_nobody_spoke_in_is_not_summarised(tmp_path: Path) -> None:
    llm = FakeLlm()
    session, _published, events = await make(tmp_path, llm=llm)
    await session.handle('{"type": "note", "text": "only a note"}')
    await session.end()
    assert llm.calls == [] and not any(event["type"] == "summary" for event in events)


async def test_summary_failure_is_reported_and_the_next_meeting_still_starts(tmp_path: Path) -> None:
    session, _published, events = await make(tmp_path, llm=FakeLlm("not json"))
    session.publish(said("hello"))
    await session.end()
    assert "error" in next(event for event in events if event["type"] == "summary")
    assert session.meeting is not None


async def test_silence_ends_the_meeting_and_can_stop_the_engine(tmp_path: Path, monkeypatch) -> None:
    import asyncio

    import continuum.session as session_module

    monkeypatch.setattr(session_module, "IDLE_CHECK_S", 0.01)
    clock, stopped = Clock(), []
    session, _published, events = await make(
        tmp_path,
        clock=clock,
        stop=lambda: stopped.append(True),
        settings={"idle_end_minutes": 5, "exit_when_idle": True},
    )
    session.publish(said("hello"))
    clock.now += 4 * 60
    watcher = asyncio.create_task(session.watch_idle())
    await asyncio.sleep(0.05)
    assert stopped == []
    clock.now += 61
    await asyncio.sleep(0.05)
    watcher.cancel()
    assert stopped == [True]
    assert {"type": "meeting_ended", "reason": "idle"} in events


async def test_recording_is_written_and_named_in_the_notes(tmp_path: Path) -> None:
    session, _published, _events = await make(tmp_path, settings={"record_audio": True, "sources": ("system",)})
    session.publish(said("hello"))
    for _ in range(10):
        session.record("system", np.full(1600, 0.2, dtype=np.float32))
    notes = session.notes_path
    await session.end()

    recording = notes.with_suffix(".wav")
    with wave.open(str(recording)) as wav:
        assert wav.getnframes() == 16_000
    assert f"<!-- continuum:audio {recording.resolve()} -->" in notes.read_text()


async def test_unused_recording_of_a_silent_meeting_is_deleted(tmp_path: Path) -> None:
    times = iter([NOW, NOW.replace(hour=10)])
    settings = Settings(notes_dir=tmp_path / "notes", record_audio=True, sources=("system",))
    session = MeetingSession(settings, now=lambda: next(times))
    await session.start()
    await session.end()

    (remaining,) = (tmp_path / "notes").glob("*.wav")
    assert remaining.name.startswith(f"{NOW.replace(hour=10).astimezone():%Y-%m-%d %H}")


@pytest.mark.parametrize("title, expected", [("Weekly sync", "Weekly sync"), (None, "Meeting")])
async def test_meeting_is_titled_from_the_calendar(tmp_path: Path, title, expected) -> None:
    session, _published, events = await make(tmp_path, title_for=lambda now: title)
    assert events[0] == {"type": "meeting_started", "title": expected}
    assert session.notes_path.name.endswith(f"{expected}.md")


async def test_closing_keeps_only_recordings_with_speech(tmp_path: Path) -> None:
    for spoken in (False, True):
        folder = tmp_path / str(spoken)
        settings = Settings(notes_dir=folder, record_audio=True, sources=("system",))
        session = MeetingSession(settings, now=lambda: NOW)
        await session.start()
        if spoken:
            session.publish(said("hello"))
        await session.close()
        assert len(list(folder.glob("*.wav"))) == int(spoken)


async def test_remembered_voices_are_named_and_named_voices_are_learned(tmp_path: Path) -> None:
    speakers = FakeSpeakers(known={"Speaker 1": "Ayşe", "Speaker 3": "Ayşe"})
    session, _published, events = await make(tmp_path, speakers=speakers)

    assert session.relabel(said("hello", "Speaker 1")).speaker == "Ayşe"
    assert session.relabel(said("hi", "Speaker 1")).words[0].speaker == "Ayşe"
    # A second voice matching the same person is not given the same name.
    assert session.relabel(said("hey", "Speaker 3")).speaker == "Speaker 3"
    await session.handle('{"type": "rename_speaker", "from": "Speaker 2", "to": "Mark"}')
    assert [e for e in events if e["type"] == "renamed"] == [
        {"type": "renamed", "from": "Speaker 1", "to": "Ayşe"},
        {"type": "renamed", "from": "Speaker 2", "to": "Mark"},
    ]

    await session.end()

    assert sorted(speakers.learned) == [("Speaker 1", "Ayşe"), ("Speaker 2", "Mark")]
    assert session.relabel(said("new meeting", "Speaker 2")).speaker == "Speaker 2"


async def test_a_calendar_meeting_gets_a_brief_and_the_user_can_ask_again(tmp_path: Path) -> None:
    import asyncio

    llm = FakeLlm("Last time: budget $35,000 [1].")
    session, _published, events = await make(
        tmp_path, memory=FakeMemory(), llm=llm, title_for=lambda now: "Budget review"
    )
    await asyncio.sleep(0.05)
    briefs = [event for event in events if event["type"] == "brief"]
    assert briefs[0]["title"] == "Budget review" and briefs[0]["sources"][0]["number"] == 1

    await session.handle('{"type": "brief"}')
    assert len([event for event in events if event["type"] == "brief"]) == 2


async def test_a_meeting_without_a_title_explains_why_there_is_no_brief(tmp_path: Path) -> None:
    session, _published, events = await make(tmp_path, memory=FakeMemory(), llm=FakeLlm())
    assert not [event for event in events if event["type"] == "brief"]
    await session.handle('{"type": "brief"}')
    assert "no calendar title" in events[-1]["error"]
