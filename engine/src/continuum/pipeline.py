# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Runs the live engine: capture, transcribe, label speakers, stream to the HUD.

This module only wires the other modules together; it holds no audio,
diarization, or transport logic of its own.
"""

import asyncio
import contextlib
import logging
import os
import signal
import sys
import threading
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import numpy as np

from continuum.audio.blocks import SAMPLE_RATE
from continuum.audio.chunker import Utterance, UtteranceChunker
from continuum.audio.transcriber import Transcriber
from continuum.config import Settings
from continuum.diarization.pyannote_diarizer import PyannoteDiarizer
from continuum.diarization.turns import label_segment
from continuum.factcheck.checker import FactCheckAlert, FactChecker
from continuum.memory.embedder import DEFAULT_MODEL, load_embedder
from continuum.memory.store import Meeting, MemoryStore
from continuum.transcript import Segment
from continuum.transport.server import TranscriptServer

logger = logging.getLogger(__name__)

BlockSource = Callable[[], AsyncIterator[np.ndarray]]


def _block_source(source: str) -> BlockSource:
    """Return the capture function for ``source``, importing it on demand.

    Raises:
        RuntimeError: if system audio is requested on an unsupported platform.
    """
    if source == "mic":
        from continuum.audio.microphone import microphone_blocks

        return microphone_blocks
    if sys.platform != "darwin":
        raise RuntimeError("System audio capture is only implemented for macOS.")
    from continuum.audio.system_audio import system_audio_blocks

    return system_audio_blocks


class Engine:
    """Turns live audio into published transcript segments.

    One model instance is shared by all sources, so model calls are serialised
    with a lock and run in worker threads to keep the event loop responsive.
    """

    def __init__(
        self,
        transcriber: Transcriber,
        publish: Callable[[Segment], None],
        diarizer: PyannoteDiarizer | None = None,
        remember: Callable[[Segment, bool], None] | None = None,
        check: Callable[[Segment], FactCheckAlert | None] | None = None,
        publish_alert: Callable[[FactCheckAlert], None] | None = None,
    ) -> None:
        self._transcriber = transcriber
        self._publish = publish
        self._diarizer = diarizer
        self._remember = remember
        self._check = check
        self._publish_alert = publish_alert
        self._model_lock = asyncio.Lock()

    async def process(self, utterance: Utterance, source: str) -> None:
        """Transcribe one utterance and publish its segments.

        System audio is additionally split by speaker when a diarizer is set;
        the microphone is always the local user. Segments are published
        first. Each is then fact-checked against memory (when ``check`` is
        set) and only afterwards written to memory (when ``remember`` is
        set), so a statement is never compared with itself. ``remember``
        receives the segment and whether it was flagged, so a contradicted
        claim is stored as disputed and cannot become the record. A failure
        in either step is logged and does not interrupt the live transcript.
        """
        async with self._model_lock:
            segments = await asyncio.to_thread(self._transcriber.transcribe, utterance, source)
            if segments and self._diarizer is not None and source == "system":
                turns = await asyncio.to_thread(self._diarizer.diarize, utterance)
                segments = [label_segment(segment, turns) for segment in segments]
        for segment in segments:
            self._publish(segment)
        for segment in segments:
            flagged = False
            if self._check is not None and self._publish_alert is not None:
                try:
                    alert = await asyncio.to_thread(self._check, segment)
                except Exception:
                    logger.exception("Could not fact-check a transcript segment")
                else:
                    if alert is not None:
                        flagged = True
                        logger.info(
                            "Fact check: said %s, on record %s", alert.claimed, alert.recorded
                        )
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


async def _run_source_logged(engine: Engine, source: str) -> bool:
    """Run one source; log instead of raising so other sources keep going."""
    try:
        await engine.run_source(source, _block_source(source)())
    except Exception:
        logger.exception("Audio source %r stopped", source)
        return False
    return True


async def run(settings: Settings) -> int:
    """Run the engine until every audio source has stopped.

    Returns a process exit code: 1 when all sources failed, otherwise 0.
    """
    logger.info("Loading Whisper model %r", settings.whisper_model)
    transcriber = await asyncio.to_thread(
        Transcriber, settings.whisper_model, settings.model_dir
    )
    diarizer = None
    if settings.hf_token:
        try:
            diarizer = await asyncio.to_thread(
                PyannoteDiarizer.from_pretrained, settings.hf_token, settings.model_dir
            )
        except RuntimeError as error:
            # Speaker separation is an enhancement; transcription must still run.
            logger.error("%s Continuing with speakers labelled by audio source only.", error)
    else:
        logger.info("HF_TOKEN is not set: speakers are labelled by audio source only")

    with contextlib.ExitStack() as stack:
        remember = None
        check = None
        if settings.scope is not None:
            model_name = settings.embedding_model or DEFAULT_MODEL
            embed, dimensions = await asyncio.to_thread(
                load_embedder, model_name, settings.model_dir
            )
            # Transcripts are private: only the current user may read the folder.
            settings.memory_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            store = stack.enter_context(MemoryStore(settings.memory_dir, embed, dimensions, model_name)
            )
            memory = store.scoped(settings.scope)
            meeting = Meeting(str(uuid.uuid4()), datetime.now(UTC))

            def remember(segment: Segment, disputed: bool) -> None:
                memory.add_segment(segment, meeting, disputed=disputed)

            check = FactChecker(memory.search).check

            logger.info(
                "Storing meeting %s for tenant %r, project %r",
                meeting.meeting_id,
                settings.scope.tenant_id,
                settings.scope.project_id,
            )
        else:
            logger.info(
                "Memory is off: set CONTINUUM_TENANT_ID and CONTINUUM_PROJECT_ID to store transcripts"
            )

        async with TranscriptServer(port=settings.ws_port) as server:
            engine = Engine(
                transcriber, server.publish, diarizer, remember, check, server.publish_alert
            )
            results = await asyncio.gather(
                *(_run_source_logged(engine, source) for source in settings.sources)
            )
    return 0 if any(results) else 1


async def _serve(settings: Settings) -> int:
    """Run the engine, stopping cleanly on SIGTERM or when the parent goes away.

    With ``CONTINUUM_EXIT_ON_STDIN_EOF=1`` the engine stops as soon as its
    standard input closes. The desktop app holds that pipe open, so the engine
    can never outlive the app and keep recording, even if the app crashes.
    """
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    assert task is not None
    with contextlib.suppress(NotImplementedError):  # signal handlers: not on Windows
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
    if os.environ.get("CONTINUUM_EXIT_ON_STDIN_EOF") == "1":

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
    """Console entry point (``continuum-engine``). Stops on Ctrl+C."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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
