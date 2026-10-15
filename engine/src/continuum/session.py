# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The meeting lifecycle of one engine run.

A session holds the current meeting: its notes file, recording, transcript
and memory id. It applies what the user does in the desktop app (notes,
speaker names, questions, ending the meeting). Ending a meeting, by the user
or after a silence, merges duplicate speakers, writes the AI summary into the
notes, queues proposed actions for approval, and starts the next meeting.
"""

import asyncio
import contextlib
import logging
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from continuum.actions.calendar import CalendarEvent
from continuum.ask import answer, brief
from continuum.audio.recorder import MixRecorder
from continuum.config import Settings
from continuum.live_controls import (
    NOTE_SOURCE,
    Ask,
    Brief,
    EndMeeting,
    Note,
    Rename,
    SpeakerNames,
    SwitchProject,
    note_segment,
    parse,
)
from continuum.llm import Llm
from continuum.memory.scope import TenantScope
from continuum.memory.store import Meeting, MemoryHit, ScopedMemory
from continuum.notes import MeetingNotes, markdown_lines
from continuum.privacy import redact_segment
from continuum.stats import speaker_stats
from continuum.stats import to_markdown as stats_markdown
from continuum.summary import MeetingSummary, summarize, to_markdown
from continuum.transcript import Segment

logger = logging.getLogger(__name__)

MAX_SEGMENTS = 20_000
"""Transcript kept per meeting for its summary (many hours of speech)."""

IDLE_CHECK_S = 15.0

LIVE_ITEMS_INTERVAL_S = 180.0
"""Least time between two live action-item updates (each is one AI call)."""


class Speakers(Protocol):
    """What the session needs from the diarizer."""

    def speaker_merges(self) -> dict[str, str]: ...
    def reset(self) -> None: ...
    def recognise(self, label: str) -> str | None: ...
    def learn(self, label: str, name: str) -> None: ...


Propose = Callable[[MeetingSummary, str, CalendarEvent | None], tuple[int, list[str]]]
"""Queues a summary's action items (``source``: the notes file; the calendar
event, if any, gives the recap e-mail's attendees and subject); returns how
many were queued and any errors."""


def queue_configured_proposals(targets: tuple[str, ...]) -> Propose:
    """Return a :data:`Propose` that queues action items to ``targets`` for approval."""

    def propose(summary: MeetingSummary, source: str, event: CalendarEvent | None) -> tuple[int, list[str]]:
        from continuum.actions import proposals
        from continuum.actions.settings import ActionSettings
        from continuum.actions.store import ActionStore
        from continuum.summarize_cli import build_proposals

        try:
            action_settings = ActionSettings.from_env(os.environ)
        except ValueError as error:
            return 0, [str(error)]
        built, errors = build_proposals(
            summary,
            list(targets),
            action_settings,
            source,
            event.attendees if event else (),
            event.title if event else "",
        )
        store = ActionStore(action_settings.database)
        queued = 0
        for proposal in built:
            try:
                proposals.queue(store, proposal)
                queued += 1
            except RuntimeError as error:
                errors.append(str(error))
        return queued, errors

    return propose


@dataclass
class _Current:
    meeting: Meeting
    event: CalendarEvent | None
    notes: MeetingNotes | None
    recorder: MixRecorder | None
    started: float
    last_speech: float
    segments: list[Segment] = field(default_factory=list)
    items_checked_at: float = 0.0
    items_checked_segments: int = 0

    @property
    def title(self) -> str | None:
        return self.event.title if self.event else None

    @property
    def spoken(self) -> bool:
        return any(segment.source != NOTE_SOURCE for segment in self.segments)


class MeetingSession:
    """The current meeting and everything the user does to it.

    Use from the event loop. :meth:`publish` and :meth:`relabel` are passed
    to the :class:`~continuum.pipeline.Engine`; :meth:`remember` too, and it
    may run in a worker thread.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        memory: ScopedMemory | None = None,
        llm: Llm | None = None,
        speakers: Speakers | None = None,
        title_for: Callable[[datetime], CalendarEvent | str | None] | None = None,
        propose: Propose | None = None,
        stop: Callable[[], None] | None = None,
        open_scope: Callable[[TenantScope], ScopedMemory] | None = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings
        self._memory = memory
        self._llm = llm
        self._speakers = speakers
        self._title_for = title_for
        self._propose = propose
        self._stop = stop
        self._open_scope = open_scope
        self._scope = settings.scope
        self._next_scope: tuple[TenantScope, ScopedMemory] | None = None
        self._clock = clock
        self._now = now
        self.names = SpeakerNames()
        self._publish_segment: Callable[[Segment], None] = lambda segment: None
        self._publish_event: Callable[[dict[str, Any]], None] = lambda event: None
        self._current: _Current | None = None
        self._ending = asyncio.Lock()
        self._asking = asyncio.Lock()
        self._briefing: asyncio.Task[None] | None = None
        self._listing: asyncio.Task[None] | None = None

    def connect(
        self,
        publish_segment: Callable[[Segment], None],
        publish_event: Callable[[dict[str, Any]], None],
    ) -> None:
        """Set where segments and events go (the transcript server)."""
        self._publish_segment = publish_segment
        self._publish_event = publish_event

    @property
    def meeting(self) -> Meeting | None:
        """The meeting being recorded now."""
        return self._current.meeting if self._current else None

    @property
    def notes_path(self) -> Path | None:
        """The current meeting's notes file, if notes are kept."""
        return self._current.notes.path if self._current and self._current.notes else None

    def search(self, query: str, limit: int = 5) -> list[MemoryHit]:
        """Search the current project's memory (empty when memory is off). Blocks."""
        memory = self._memory
        return memory.search(query, limit) if memory is not None else []

    # --- starting and stopping -------------------------------------------------

    async def start(self) -> None:
        """Begin a new meeting, titled after the calendar event happening now, if any.

        A project switch the user asked for takes effect here, so a meeting is
        never split across two projects.
        """
        if self._next_scope is not None:
            self._scope, self._memory = self._next_scope
            self._next_scope = None
        started_at = self._now()
        event = None
        if self._title_for is not None:
            try:
                found = await asyncio.to_thread(self._title_for, started_at)
            except Exception:
                logger.exception("Could not read the calendar for a meeting title")
            else:
                event = CalendarEvent(found) if isinstance(found, str) else found
        title = event.title if event else None
        notes = recorder = None
        if self._settings.notes_dir is not None:
            directory = self._settings.notes_dir
            if self._scope is not None:
                directory = directory / self._scope.tenant_id / self._scope.project_id
            notes = MeetingNotes(
                directory, started_at, title or "Meeting", attendees=event.attendees if event else ()
            )
            if self._settings.record_audio:
                try:
                    recorder = MixRecorder(notes.path.with_suffix(".wav"), self._settings.sources)
                    notes.set_audio(recorder.path)
                except OSError:
                    logger.exception("Could not start recording")
            logger.info("Writing meeting notes to %s", notes.path)
        now = self._clock()
        self._current = _Current(Meeting(str(uuid.uuid4()), started_at), event, notes, recorder, now, now)
        started: dict[str, Any] = {"type": "meeting_started", "title": title or "Meeting"}
        if self._scope is not None:
            started["project"] = self._scope.project_id
        self._publish_event(started)
        if title and self._memory is not None and self._llm is not None:
            # A calendar meeting gets its brief without blocking the transcript.
            self._briefing = asyncio.create_task(self._brief())

    async def end(self, reason: str = "user") -> None:
        """Finish the current meeting and, unless the engine should stop, start the next.

        A meeting in which nobody spoke is not summarised. Failures in any
        step are logged and reported to the app; the next meeting still starts.
        """
        async with self._ending:
            current = self._current
            if current is None:
                return
            ended: dict[str, Any] = {"type": "meeting_ended", "reason": reason}
            if current.spoken:
                await self._merge_duplicate_speakers(current)
                if current.recorder is not None:
                    current.recorder.close()
                ended["talk_time"] = self._talk_time(current)
                await self._summarise(current)
            elif current.recorder is not None:
                current.recorder.close()
                with contextlib.suppress(OSError):
                    current.recorder.path.unlink()
            self._learn_voices()
            self._publish_event(ended)
            if self._speakers is not None:
                self._speakers.reset()
            self.names = SpeakerNames()
            self._current = None
            if reason == "idle" and self._settings.exit_when_idle and self._stop is not None:
                logger.info("Meeting ended after silence; stopping the engine")
                self._stop()
                return
            await self.start()

    async def watch_idle(self) -> None:
        """End the meeting after ``idle_end_minutes`` without speech. Runs until cancelled."""
        minutes = self._settings.idle_end_minutes
        if minutes is None:
            return
        while True:
            await asyncio.sleep(IDLE_CHECK_S)
            current = self._current
            if current and current.spoken and self._clock() - current.last_speech >= minutes * 60:
                await self.end("idle")

    async def close(self) -> None:
        """Finish the recording when the engine stops (no summary: the app is closing).

        The recording of a meeting in which nobody spoke is deleted.
        """
        self._learn_voices()
        current = self._current
        if current is None or current.recorder is None:
            return
        current.recorder.close()
        if not current.spoken:
            with contextlib.suppress(OSError):
                current.recorder.path.unlink()

    # --- live transcript -------------------------------------------------------

    def relabel(self, segment: Segment) -> Segment:
        """Apply the names the user gave to speakers, and recognise remembered voices."""
        if self._speakers is not None:
            labels = {segment.speaker, *(word.speaker for word in segment.words)}
            for label in sorted(label for label in labels if label and label.startswith("Speaker ")):
                self._recognise(label)
        return self.names.apply(segment)

    def _recognise(self, label: str) -> None:
        assert self._speakers is not None
        if self.names.shown(label) != label:
            return
        name = self._speakers.recognise(label)
        if name is None or name in self.names.named().values():
            return
        self.names.rename(label, name)
        logger.info("Recognised %s as %s", label, name)
        self._publish_event({"type": "renamed", "from": label, "to": name})

    def _learn_voices(self) -> None:
        """Remember the voices of named speakers for the next meetings."""
        if self._speakers is None:
            return
        for label, name in self.names.named().items():
            if name.startswith("Speaker "):
                continue
            try:
                self._speakers.learn(label, name)
            except OSError:
                logger.exception("Could not remember the voice of %s", name)

    def publish(self, segment: Segment) -> None:
        """Show ``segment`` live, add it to the notes (redacted) and the meeting's transcript."""
        self._publish_segment(segment)
        current = self._current
        if current is None:
            return
        if len(current.segments) < MAX_SEGMENTS:
            current.segments.append(segment)
        if segment.source != NOTE_SOURCE:
            current.last_speech = self._clock()
        if current.notes is not None:
            try:
                current.notes.add(redact_segment(segment) if self._settings.redact else segment)
            except OSError:
                logger.exception("Could not write meeting notes")
        self._maybe_list_items(current)

    def _maybe_list_items(self, current: _Current) -> None:
        """Start a live action-item update when enough time and new speech have passed."""
        if not self._settings.live_action_items or self._llm is None:
            return
        if self._listing is not None and not self._listing.done():
            return
        now = self._clock()
        if now - max(current.items_checked_at, current.started) < LIVE_ITEMS_INTERVAL_S:
            return
        if len(current.segments) <= current.items_checked_segments or not current.spoken:
            return
        current.items_checked_at = now
        current.items_checked_segments = len(current.segments)
        self._listing = asyncio.create_task(self._list_items(current))

    async def _list_items(self, current: _Current) -> None:
        """Publish the action items said so far in ``current`` (AI failures are only logged)."""
        try:
            summary = await asyncio.to_thread(summarize, self._transcript(current), self._llm, self._now().date())
        except (ValueError, RuntimeError) as error:
            logger.warning("Could not list action items during the meeting: %s", error)
            return
        if self._current is not current:
            return
        items = [{"task": item.task, "owner": item.owner, "due": item.due} for item in summary.action_items]
        self._publish_event({"type": "action_items", "items": items})

    def _transcript(self, current: _Current) -> str:
        """The meeting's transcript as the AI provider gets it: the (redacted) notes lines."""
        clean = redact_segment if self._settings.redact else (lambda segment: segment)
        return "\n".join(line for segment in current.segments for line in markdown_lines(clean(segment)))

    def remember(self, segment: Segment, disputed: bool) -> None:
        """Store ``segment`` in memory under the current meeting (redacted). Blocks."""
        current = self._current
        if self._memory is None or current is None:
            return
        stored = redact_segment(segment) if self._settings.redact else segment
        self._memory.add_segment(stored, current.meeting, disputed=disputed)

    def record(self, source: str, block: np.ndarray) -> None:
        """Add captured audio to the meeting's recording, when recording is on."""
        if self._current is not None and self._current.recorder is not None:
            self._current.recorder.feed(source, block)

    # --- messages from the desktop app -------------------------------------------

    async def handle(self, raw: str) -> None:
        """Handle one message from the desktop app; malformed ones are ignored."""
        command = parse(raw)
        if command is None:
            logger.warning("Ignored a malformed message from the desktop app")
        elif isinstance(command, Ask):
            await self._answer(command)
        elif isinstance(command, EndMeeting):
            await self.end("user")
        elif isinstance(command, Brief):
            await self._brief()
        elif isinstance(command, SwitchProject):
            await self._switch_project(command.project)
        else:
            await self._note(command)

    async def _switch_project(self, project: str) -> None:
        """End the meeting and file the next ones under ``project`` (same workspace)."""
        error = None
        if self._scope is None or self._open_scope is None:
            error = "Memory is off: set a workspace and project in Settings first."
        else:
            try:
                scope = TenantScope(self._scope.tenant_id, project)
            except ValueError as invalid:
                error = str(invalid)
            else:
                if scope == self._scope:
                    return
                try:
                    memory = await asyncio.to_thread(self._open_scope, scope)
                except Exception:
                    logger.exception("Could not open the memory of project %r", project)
                    error = f"Could not open the memory of project {project!r}."
                else:
                    logger.info("Switching to project %r", project)
                    self._next_scope = (scope, memory)
                    if self._current is None:
                        await self.start()
                    else:
                        await self.end("project")
                    return
        self._publish_event({"type": "project_error", "error": error})

    async def _note(self, command: Note | Rename) -> None:
        if isinstance(command, Rename):
            self.names.rename(command.old, command.new)
            self._publish_event({"type": "renamed", "from": command.old, "to": command.new})
            command = Note(f"{command.old} is now called {command.new}.")
        started = self._current.started if self._current else self._clock()
        segment = note_segment(command, self._clock() - started)
        self.publish(segment)
        try:
            await asyncio.to_thread(self.remember, segment, False)
        except Exception:
            logger.exception("Could not store a note in memory")

    async def _answer(self, command: Ask) -> None:
        reply: dict[str, Any] = {"type": "answer", "id": command.request_id}
        if self._memory is None:
            reply["error"] = "Memory is off: set a workspace and project in Settings."
        elif self._llm is None:
            reply["error"] = "No AI model is configured: choose a provider in Settings."
        else:
            memory, llm = self._memory, self._llm
            async with self._asking:
                try:
                    result = await asyncio.to_thread(answer, command.question, memory.search, llm)
                except (ValueError, RuntimeError) as error:
                    reply["error"] = str(error)
                else:
                    reply.update(result.to_dict())
        self._publish_event(reply)

    async def _brief(self) -> None:
        """Publish a brief for the current meeting from what was said in earlier ones."""
        current = self._current
        reply: dict[str, Any] = {"type": "brief"}
        if current is None or not current.title:
            reply["error"] = "This meeting has no calendar title to look up; ask a question instead."
        elif self._memory is None:
            reply["error"] = "Memory is off: set a workspace and project in Settings."
        elif self._llm is None:
            reply["error"] = "No AI model is configured: choose a provider in Settings."
        else:
            memory, llm, title = self._memory, self._llm, current.title
            reply["title"] = title
            async with self._asking:
                try:
                    result = await asyncio.to_thread(brief, title, memory.search, llm)
                except (ValueError, RuntimeError) as error:
                    reply["error"] = str(error)
                else:
                    reply.update(result.to_dict())
        self._publish_event(reply)

    # --- ending a meeting ----------------------------------------------------------

    def _talk_time(self, current: _Current) -> list[dict[str, Any]]:
        """Add each speaker's talk time to the notes and return it for the app."""
        stats = speaker_stats(current.segments)
        if current.notes is not None and stats:
            try:
                current.notes.append(stats_markdown(stats))
            except OSError:
                logger.exception("Could not add talk time to the notes")
        return [
            {
                "speaker": s.speaker,
                "seconds": round(s.talk_s, 1),
                "share": round(s.share, 3),
                "longest_seconds": round(s.longest_s, 1),
                "interruptions": s.interruptions,
            }
            for s in stats
        ]

    async def _merge_duplicate_speakers(self, current: _Current) -> None:
        if self._speakers is None:
            return
        merges = {
            self.names.shown(old): self.names.shown(new)
            for old, new in self._speakers.speaker_merges().items()
        }
        merges = {old: new for old, new in merges.items() if old != new}
        if not merges:
            return
        logger.info("Merging duplicate speakers: %s", merges)
        current.segments = [_rename(segment, merges) for segment in current.segments]
        try:
            if current.notes is not None:
                current.notes.rename_speakers(merges)
            if self._memory is not None:
                for old, new in merges.items():
                    await asyncio.to_thread(self._memory.rename_speaker, current.meeting.meeting_id, old, new)
        except Exception:
            logger.exception("Could not merge duplicate speakers everywhere")
        for old, new in merges.items():
            self._publish_event({"type": "renamed", "from": old, "to": new})

    async def _summarise(self, current: _Current) -> None:
        if self._llm is None:
            return
        event: dict[str, Any] = {"type": "summary"}
        try:
            summary = await asyncio.to_thread(summarize, self._transcript(current), self._llm, self._now().date())
        except (ValueError, RuntimeError) as error:
            event["error"] = str(error)
            self._publish_event(event)
            return
        markdown = to_markdown(summary)
        event["markdown"] = markdown
        if current.notes is not None:
            try:
                current.notes.append(markdown)
            except OSError:
                logger.exception("Could not add the summary to the notes")
        if self._propose is not None and self._settings.auto_propose:
            source = current.notes.path.name if current.notes else "the meeting"
            queued, errors = await asyncio.to_thread(self._propose, summary, source, current.event)
            event.update(queued=queued, errors=errors)
        self._publish_event(event)


def _rename(segment: Segment, names: dict[str, str]) -> Segment:
    words = tuple(
        replace(word, speaker=names.get(word.speaker, word.speaker)) if word.speaker else word
        for word in segment.words
    )
    return replace(segment, speaker=names.get(segment.speaker, segment.speaker), words=words)
