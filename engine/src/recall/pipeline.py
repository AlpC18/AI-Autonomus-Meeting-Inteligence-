# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Runs the live engine: capture, transcribe, label speakers, stream to the HUD.

This module only wires the other modules together; it holds no audio,
diarization, or transport logic of its own.
"""

import asyncio
import contextlib
import functools
import logging
import os
import signal
import sys
import threading
from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime, timedelta

import numpy as np

from recall import net
from recall.actions.calendar import CalendarEvent, current_event
from recall.actions.settings import ActionSettings
from recall.audio.blocks import SAMPLE_RATE
from recall.audio.chunker import Utterance, UtteranceChunker
from recall.audio.transcriber import SpeechToText, load_transcriber
from recall.config import Settings
from recall.context.code import CodeContext, CodeIndex
from recall.context.risk import RiskTracker, WorkloadLookup
from recall.context.workload import (
    GitHubWorkload,
    GitLabWorkload,
    JiraWorkload,
    combined,
)
from recall.diagnostics import log_to_file
from recall.diarization.pyannote_diarizer import PyannoteDiarizer
from recall.diarization.turns import label_segment
from recall.diarization.voices import VoiceBook
from recall.factcheck.checker import FactCheckAlert, FactChecker
from recall.factcheck.semantic import SemanticChecker
from recall.llm import Llm, LlmSettings, connect
from recall.memory.embedder import DEFAULT_MODEL, load_embedder
from recall.memory.scope import TenantScope
from recall.memory.store import MemoryHit, MemoryStore, ScopedMemory
from recall.privacy import storage_settings, warn_if_disk_unencrypted
from recall.session import MeetingSession, Watcher, queue_configured_proposals
from recall.transcript import Segment
from recall.transport.server import TranscriptServer

logger = logging.getLogger(__name__)

BlockSource = Callable[[], AsyncIterator[np.ndarray]]


def _block_source(source: str, settings: Settings) -> BlockSource:
    """Return the capture function for ``source``, importing it on demand.

    System audio uses ScreenCaptureKit on macOS and speaker loopback
    (``soundcard``) on Windows and Linux. ``meeting_apps_only`` limits
    system audio to meeting apps; only macOS can do that. With browser tab
    audio on, a browser call comes from the extension (``tab``), so on macOS
    system audio is limited to the meeting apps that are not browsers.
    """
    if source == "mic":
        from recall.audio.microphone import microphone_blocks

        return microphone_blocks
    if source == "tab":
        from recall.audio.browser_tab import tab_audio_blocks

        return functools.partial(tab_audio_blocks, extension_id=settings.browser_extension_id)
    if sys.platform != "darwin":
        from recall.audio.loopback import loopback_blocks

        if sys.platform == "win32" and (settings.meeting_apps_only or settings.browser_tab_audio):
            from recall.audio.process_loopback import process_loopback_blocks
            from recall.audio.windows_apps import BROWSER_EXES, NATIVE_MEETING_EXES

            extra = frozenset(app.lower() for app in settings.extra_meeting_apps if app.lower().endswith(".exe"))
            browsers = frozenset() if settings.browser_tab_audio else BROWSER_EXES
            return functools.partial(
                _with_fallback,
                functools.partial(process_loopback_blocks, NATIVE_MEETING_EXES | extra, browsers),
                loopback_blocks,
            )
        if sys.platform.startswith("linux") and (settings.meeting_apps_only or settings.browser_tab_audio):
            from recall.audio.pulse_apps import (
                BROWSER_BINARIES,
                NATIVE_MEETING_BINARIES,
                pulse_app_blocks,
            )

            extra = frozenset(app.lower() for app in settings.extra_meeting_apps if "." not in app)
            browsers = frozenset() if settings.browser_tab_audio else BROWSER_BINARIES
            return functools.partial(
                _with_fallback,
                functools.partial(pulse_app_blocks, NATIVE_MEETING_BINARIES | extra, browsers),
                loopback_blocks,
            )
        return loopback_blocks
    from recall.audio.apps import MEETING_APPS, NATIVE_MEETING_APPS
    from recall.audio.system_audio import system_audio_blocks

    if settings.browser_tab_audio:
        return functools.partial(system_audio_blocks, True, NATIVE_MEETING_APPS | settings.extra_meeting_apps)
    return functools.partial(
        system_audio_blocks, settings.meeting_apps_only, MEETING_APPS | settings.extra_meeting_apps
    )


async def _with_fallback(primary: BlockSource, fallback: BlockSource) -> AsyncIterator[np.ndarray]:
    """``primary``'s blocks; ``fallback``'s if ``primary`` fails before its first block."""
    blocks = primary()
    try:
        first = await anext(blocks)
    except StopAsyncIteration:
        return
    except Exception as error:  # noqa: BLE001 - any start-up failure means: use the fallback
        logger.warning("Capturing all system audio instead of only the meeting app: %s", error)
        async for block in fallback():
            yield block
        return
    yield first
    async for block in blocks:
        yield block


class Engine:
    """Turns live audio into published transcript segments.

    One model instance is shared by all sources, so model calls are serialised
    with a lock and run in worker threads to keep the event loop responsive.
    """

    def __init__(
        self,
        transcriber: SpeechToText,
        publish: Callable[[Segment], None],
        diarizer: PyannoteDiarizer | None = None,
        remember: Callable[[Segment, bool], None] | None = None,
        check: Callable[[Segment], FactCheckAlert | None] | None = None,
        publish_alert: Callable[[FactCheckAlert], None] | None = None,
        relabel: Callable[[Segment], Segment] | None = None,
    ) -> None:
        self._transcriber = transcriber
        self._publish = publish
        self._diarizer = diarizer
        self._remember = remember
        self._check = check
        self._publish_alert = publish_alert
        self._relabel = relabel
        self._model_lock = asyncio.Lock()

    async def process(self, utterance: Utterance, source: str) -> None:
        """Transcribe one utterance and publish its segments.

        System audio and a browser tab are additionally split by speaker when a diarizer is set;
        the microphone is always the local user. ``relabel`` then applies the
        names the user gave to speakers. Segments are published
        first. Each is then fact-checked against memory (when ``check`` is
        set) and only afterwards written to memory (when ``remember`` is
        set), so a statement is never compared with itself. ``remember``
        receives the segment and whether it was flagged, so a contradicted
        claim is stored as disputed and cannot become the record. A failure
        in either step is logged and does not interrupt the live transcript.
        """
        async with self._model_lock:
            segments = await asyncio.to_thread(self._transcriber.transcribe, utterance, source)
            if segments and self._diarizer is not None and source != "mic":
                turns = await asyncio.to_thread(self._diarizer.diarize, utterance)
                segments = [label_segment(segment, turns) for segment in segments]
        if self._relabel is not None:
            segments = [self._relabel(segment) for segment in segments]
        for segment in segments:
            self._publish(segment)
        for segment in segments:
            await self.check_and_remember(segment)

    async def check_and_remember(self, segment: Segment) -> None:
        """Fact-check ``segment`` against memory, then store it (as disputed when flagged).

        Also used for text read from shared slides, which is not part of the transcript.
        """
        flagged = False
        if self._check is not None and self._publish_alert is not None:
            try:
                alert = await asyncio.to_thread(self._check, segment)
            except Exception:
                logger.exception("Could not fact-check a transcript segment")
            else:
                if alert is not None:
                    flagged = True
                    logger.info("Fact check: said %s, on record %s", alert.claimed, alert.recorded)
                    self._publish_alert(alert)
        if self._remember is not None:
            try:
                await asyncio.to_thread(self._remember, segment, flagged)
            except Exception:
                logger.exception("Could not store a transcript segment in memory")

    async def run_source(self, source: str, blocks: AsyncIterator[np.ndarray]) -> None:
        """Consume ``blocks`` from ``source`` until the stream ends or fails."""
        chunker = UtteranceChunker(SAMPLE_RATE)
        async for block in blocks:
            for utterance in chunker.feed(block):
                await self.process(utterance, source)


async def _tapped(
    blocks: AsyncIterator[np.ndarray], source: str, record: Callable[[str, np.ndarray], None]
) -> AsyncIterator[np.ndarray]:
    """Pass ``blocks`` through, handing each to ``record`` first."""
    async for block in blocks:
        record(source, block)
        yield block


async def _run_source_logged(
    engine: Engine,
    source: str,
    record: Callable[[str, np.ndarray], None],
    settings: Settings,
) -> bool:
    """Run one source; log instead of raising so other sources keep going."""
    try:
        blocks = _block_source(source, settings)()
        await engine.run_source(source, _tapped(blocks, source, record))
    except Exception:
        logger.exception("Audio source %r stopped", source)
        return False
    return True


def _load_llm() -> Llm | None:
    """The configured AI model, or ``None`` (logged) when there is none or it is unusable."""
    try:
        llm_settings = LlmSettings.from_env(os.environ)
        return connect(llm_settings) if llm_settings else None
    except (ValueError, RuntimeError) as error:
        logger.error("AI model not available: %s", error)
        return None


def _calendar_title() -> Callable[[datetime], CalendarEvent | None] | None:
    """Looks up the current calendar event when Google Calendar is configured."""
    try:
        action_settings = ActionSettings.from_env(os.environ)
    except ValueError:
        return None
    access = action_settings.google
    if access is None:
        return None

    def title_for(now: datetime) -> CalendarEvent | None:
        with net.client(10) as client:
            return current_event(access, action_settings.google_calendar_id, client, now)

    return title_for


async def run(settings: Settings) -> int:
    """Run the engine until every audio source has stopped.

    Returns a process exit code: 1 when all sources failed, otherwise 0.
    """
    settings = storage_settings(settings)
    logger.info("Loading Whisper model %r (%s)", settings.whisper_model, settings.asr_backend)
    try:
        transcriber = await asyncio.to_thread(
            load_transcriber, settings.asr_backend, settings.whisper_model, settings.model_dir
        )
    except OSError as error:
        # Model downloads fail as OSError subclasses (no connection, TLS errors).
        raise RuntimeError(
            f"Could not load the speech model {settings.whisper_model!r}. The first start "
            f"downloads it, which needs an internet connection. ({type(error).__name__})"
        ) from error
    diarizer = None
    if settings.hf_token:
        try:
            voices = VoiceBook(settings.voices_file) if settings.remember_voices else None
            diarizer = await asyncio.to_thread(
                PyannoteDiarizer.from_pretrained, settings.hf_token, settings.model_dir, voices
            )
        except RuntimeError as error:
            # Speaker separation is an enhancement; transcription must still run.
            logger.error("%s Continuing with speakers labelled by audio source only.", error)
    else:
        logger.info("HF_TOKEN is not set: speakers are labelled by audio source only")
    llm = _load_llm()

    if settings.scope is not None or settings.notes_dir is not None:
        warn_if_disk_unencrypted()
    with contextlib.ExitStack() as stack:
        memory = None
        open_scope = None
        if settings.scope is not None:
            model_name = settings.embedding_model or DEFAULT_MODEL
            embed, dimensions = await asyncio.to_thread(
                load_embedder, model_name, settings.model_dir
            )
            # Transcripts are private: only the current user may read the folder.
            settings.memory_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            store = stack.enter_context(MemoryStore(settings.memory_dir, embed, dimensions, model_name))
            open_scope = _scope_opener(store, settings.retention_days)
            memory = await asyncio.to_thread(open_scope, settings.scope)
            logger.info(
                "Storing meetings for tenant %r, project %r",
                settings.scope.tenant_id,
                settings.scope.project_id,
            )
        else:
            logger.info(
                "Memory is off: set RECALL_TENANT_ID and RECALL_PROJECT_ID to store transcripts"
            )

        main_task = asyncio.current_task()
        assert main_task is not None
        session = MeetingSession(
            settings,
            memory=memory,
            llm=llm,
            speakers=diarizer,
            title_for=_calendar_title(),
            propose=queue_configured_proposals(settings.auto_propose) if settings.auto_propose else None,
            stop=main_task.cancel,
            open_scope=open_scope,
            watchers=await _watchers(settings, stack, llm),
        )
        check = _checker(session.search, llm if settings.llm_fact_check else None) if memory else None
        async with TranscriptServer(port=settings.ws_port, on_message=session.handle) as server:
            session.connect(server.publish, server.publish_event)
            await session.start()
            engine = Engine(
                transcriber,
                session.publish,
                diarizer,
                session.remember if memory is not None else None,
                check,
                server.publish_alert,
                session.relabel,
            )
            idle = asyncio.create_task(session.watch_idle())
            slides = _watch_slides(settings, engine) if check is not None else None
            try:
                results = await asyncio.gather(
                    *(
                        _run_source_logged(engine, source, session.record, settings)
                        for source in settings.sources
                    )
                )
            finally:
                idle.cancel()
                if slides is not None:
                    slides.cancel()
                await session.close()
    return 0 if any(results) else 1


def _watch_slides(settings: Settings, engine: Engine) -> asyncio.Task[None] | None:
    """Start fact-checking shared slides, when turned on (macOS only)."""
    if not settings.screen_fact_check:
        return None
    if sys.platform != "darwin":
        logger.warning("Fact-checking shared slides needs macOS")
        return None
    from recall.screen import watch_slides

    logger.info("Fact-checking figures on shared slides (read on this computer)")
    return asyncio.create_task(watch_slides(engine.check_and_remember))


async def _watchers(settings: Settings, stack: contextlib.ExitStack, llm: Llm | None) -> list[Watcher]:
    """The live hints the settings turn on (an HTTP client, if any, closes with ``stack``)."""
    watchers: list[Watcher] = []
    if settings.code_dirs:
        index = await asyncio.to_thread(CodeIndex.build, settings.code_dirs)
        watchers.append(CodeContext(index))
    if settings.risk_tracking:
        hesitation_llm = llm if settings.llm_hesitations else None
        watchers.append(RiskTracker(date.today, _workload(settings, stack), hesitation_llm))
    return watchers


def _workload(settings: Settings, stack: contextlib.ExitStack) -> WorkloadLookup | None:
    """Jira, GitHub and GitLab workload lookups, when turned on and those trackers are configured."""
    if not settings.workload_check:
        return None
    try:
        actions = ActionSettings.from_env(os.environ)
    except ValueError as error:
        logger.error("Workload check is off: %s", error)
        return None
    lookups: list[WorkloadLookup] = []
    client = stack.enter_context(net.client(10))
    if actions.jira is not None:
        lookups.append(JiraWorkload(actions.jira, client))
    if actions.github_token and actions.github_repos:
        lookups.append(GitHubWorkload(actions.github_token, sorted(actions.github_repos), client))
    if actions.gitlab is not None and actions.gitlab_projects:
        lookups.append(GitLabWorkload(actions.gitlab, sorted(actions.gitlab_projects), client))
    if not lookups:
        logger.warning(
            "Workload check needs Jira (RECALL_JIRA_SITE, JIRA_EMAIL, JIRA_API_TOKEN), "
            "GitHub (GITHUB_TOKEN and RECALL_GITHUB_REPOS) or GitLab (GITLAB_TOKEN and "
            "RECALL_GITLAB_PROJECTS)"
        )
        return None
    return lookups[0] if len(lookups) == 1 else combined(lookups)


def _scope_opener(store: MemoryStore, retention_days: int | None) -> Callable[[TenantScope], ScopedMemory]:
    """Opens a project's memory, first forgetting what is older than ``retention_days``. Blocks."""

    def open_scope(scope: TenantScope) -> ScopedMemory:
        memory = store.scoped(scope)
        if retention_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=retention_days)
            forgotten = memory.forget_before(cutoff)
            logger.info("Forgot %d segments older than %d days", forgotten, retention_days)
        return memory

    return open_scope


def _checker(
    search: Callable[[str, int], list[MemoryHit]], llm: Llm | None
) -> Callable[[Segment], FactCheckAlert | None]:
    """Figures first; then, when an AI model is given, contradictions without figures.

    ``search`` is the session's, so checks follow a project switch.
    """
    figures = FactChecker(search).check
    if llm is None:
        return figures
    semantic = SemanticChecker(search, llm).check
    return lambda segment: figures(segment) or semantic(segment)


async def _serve(settings: Settings) -> int:
    """Run the engine, stopping cleanly on SIGTERM or when the parent goes away.

    With ``RECALL_EXIT_ON_STDIN_EOF=1`` the engine stops as soon as its
    standard input closes. The desktop app holds that pipe open, so the engine
    can never outlive the app and keep recording, even if the app crashes.
    """
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    assert task is not None
    with contextlib.suppress(NotImplementedError):  # signal handlers: not on Windows
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
    if os.environ.get("RECALL_EXIT_ON_STDIN_EOF") == "1":

        def wait_for_parent() -> None:
            with contextlib.suppress(OSError, ValueError):
                while sys.stdin.buffer.read(4096):
                    pass
            loop.call_soon_threadsafe(task.cancel)

        threading.Thread(target=wait_for_parent, daemon=True).start()
    try:
        return await run(settings)
    except asyncio.CancelledError:
        logger.info("Engine stopping")
        return 0


def main() -> None:
    """Console entry point (``recall-engine``). Stops on Ctrl+C."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log_to_file()
    try:
        settings = Settings.from_env(os.environ)
    except ValueError as error:
        sys.exit(f"Invalid configuration: {error}")
    try:
        sys.exit(asyncio.run(_serve(settings)))
    except (RuntimeError, ValueError) as error:
        sys.exit(str(error))
    except KeyboardInterrupt:
        sys.exit(0)
