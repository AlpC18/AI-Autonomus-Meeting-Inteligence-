# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Transcribes recordings from disk, with the same models as live capture.

One file, or every new recording dropped into a watched folder. With
``--remember`` the transcript is also added to the configured memory, so
older meetings recorded elsewhere become searchable and fact-checkable.
"""

import argparse
import asyncio
import hashlib
import logging
import os
import sys
import time
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import av
import numpy as np

from recall.audio.blocks import SAMPLE_RATE
from recall.audio.transcriber import SpeechToText, load_transcriber
from recall.config import Settings
from recall.diarization.pyannote_diarizer import PyannoteDiarizer
from recall.llm import Llm, LlmSettings, connect
from recall.memory.store import Meeting
from recall.notes import markdown_lines, speaker_runs, srt, vtt
from recall.pipeline import Engine
from recall.privacy import redact_segment
from recall.summary import summarize, to_markdown
from recall.templates import for_meeting
from recall.transcript import Segment

logger = logging.getLogger(__name__)

_BLOCK = SAMPLE_RATE // 10

MEDIA_SUFFIXES = frozenset(
    {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aiff", ".aif", ".webm", ".mp4", ".mov", ".mkv"}
)
"""Files the watcher picks up; anything ffmpeg decodes works when named explicitly."""

AUDIO_MARKER = "<!-- recall:audio "
"""Starts the comment in Markdown output that names the recording, for playback."""

Remember = Callable[[list[Segment], Path], int]


async def transcribe_samples(
    samples: np.ndarray, transcriber: SpeechToText, diarizer: PyannoteDiarizer | None
) -> list[Segment]:
    """Run mono 16 kHz ``samples`` through the engine and return the segments.

    The audio is cut into utterances exactly as live system audio is, so
    speakers are separated and named when ``diarizer`` is given.
    """
    segments: list[Segment] = []

    async def blocks():
        # Trailing silence makes the chunker emit the last utterance.
        padded = np.concatenate([samples, np.zeros(2 * SAMPLE_RATE, dtype=np.float32)])
        for start in range(0, padded.size, _BLOCK):
            yield padded[start : start + _BLOCK]

    await Engine(transcriber, segments.append, diarizer).run_source("system", blocks())
    return segments


def decode_audio(path: Path) -> np.ndarray:
    """Read the first audio track of ``path`` as mono float32 at 16 kHz.

    Raises:
        av.FFmpegError: if the file cannot be opened or decoded.
        IndexError: if the file has no audio track.
        ValueError: if the audio track is empty.
    """
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks = []
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            chunks.extend(out.to_ndarray().reshape(-1) for out in resampler.resample(frame))
        chunks.extend(out.to_ndarray().reshape(-1) for out in resampler.resample(None))
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def render(segments: list[Segment], fmt: str, recording: Path | None = None) -> str:
    """Format ``segments`` as ``md``, ``srt``, ``vtt`` or ``txt``.

    Markdown made from a ``recording`` starts with a heading and a comment
    naming the file, so the transcript viewer can play it back.
    """
    if fmt == "srt":
        return srt(segments)
    if fmt == "vtt":
        return vtt(segments)
    if fmt == "txt":
        return "".join(
            f"{speaker}: {text}\n"
            for segment in segments
            for speaker, _start, text in speaker_runs(segment)
        )
    lines = "".join(line + "\n" for segment in segments for line in markdown_lines(segment))
    if recording is None:
        return lines
    # "-->" would end the comment early; such paths are left out rather than mangled.
    marker = "" if "-->" in str(recording) else f"{AUDIO_MARKER}{recording.resolve()} -->\n\n"
    return f"# {recording.stem}\n\n{marker}{lines}"


def with_summary(notes: str, llm: Llm) -> str:
    """``notes`` with the AI summary appended; unchanged if summarising fails.

    A failed summary is logged, not raised: the transcript is still worth
    keeping, and the library can summarise it later.
    """
    try:
        title = next((line[2:].strip() for line in notes.splitlines() if line.startswith("# ")), None)
        summary = summarize(notes, llm, today=date.today(), template=for_meeting(title))
    except (ValueError, RuntimeError) as error:
        logger.warning("Not summarised: %s", error)
        return notes
    return notes + "\n" + to_markdown(summary)


def meeting_for(path: Path, recorded_at: datetime | None) -> Meeting:
    """The memory meeting of a recording: its id comes from the file's content.

    Importing the same recording again therefore replaces its segments
    instead of duplicating them. Without ``recorded_at`` the file's
    modification time is used.
    """
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    started = recorded_at or datetime.fromtimestamp(path.stat().st_mtime, UTC)
    return Meeting(str(uuid.UUID(digest.hexdigest()[:32])), started)


def memory_writer(settings: Settings, recorded_at: datetime | None) -> Remember:
    """Return a function that stores a recording's segments in the configured memory.

    The embedding model is loaded once; the database is opened only while
    a recording is stored, so a long-running watcher does not lock it.

    Raises:
        LookupError: if no tenant and project are configured.
    """
    if settings.scope is None:
        raise LookupError("--remember needs RECALL_TENANT_ID and RECALL_PROJECT_ID.")
    from recall.memory.embedder import DEFAULT_MODEL, load_embedder
    from recall.memory.store import MemoryStore

    model_name = settings.embedding_model or DEFAULT_MODEL
    embed, dimensions = load_embedder(model_name, settings.model_dir)
    scope = settings.scope

    def remember(segments: list[Segment], path: Path) -> int:
        meeting = meeting_for(path, recorded_at)
        settings.memory_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        with MemoryStore(settings.memory_dir, embed, dimensions, model_name) as store:
            memory = store.scoped(scope)
            for segment in segments:
                memory.add_segment(redact_segment(segment) if settings.redact else segment, meeting)
        return len(segments)

    return remember


def write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path``, creating missing folders (readable by this user only)."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def output_path(recording: Path, fmt: str, output_dir: Path | None) -> Path:
    """Where the watcher writes the transcript of ``recording``."""
    return (output_dir or recording.parent) / f"{recording.stem}.{fmt}"


def watch(
    folder: Path,
    transcribe: Callable[[Path], list[Segment]],
    write: Callable[[Path, list[Segment]], None],
    already_done: Callable[[Path], bool],
    interval: float,
    rounds: int | None = None,
) -> None:
    """Transcribe each new recording in ``folder`` once its size stops changing.

    A file counts as finished when its size is the same on two scans in a
    row, so a recording still being written or copied is not cut short.
    Files already transcribed (``already_done``) and files that failed are
    skipped. Runs until interrupted, or for ``rounds`` scans (for tests).
    """
    sizes: dict[Path, int] = {}
    failed: set[Path] = set()
    scans = 0
    while rounds is None or scans < rounds:
        scans += 1
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in MEDIA_SUFFIXES or path in failed or not path.is_file():
                continue
            if already_done(path):
                continue
            size = path.stat().st_size
            if sizes.get(path) != size:
                sizes[path] = size
                continue
            try:
                write(path, transcribe(path))
            except Exception:
                logger.exception("Could not transcribe %s; it will not be retried", path)
                failed.add(path)
        if rounds is None or scans < rounds:
            time.sleep(interval)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe audio or video recordings.")
    parser.add_argument("file", type=Path, nargs="?", help="recording to transcribe")
    parser.add_argument("--format", choices=("md", "srt", "vtt", "txt"), default="md")
    parser.add_argument("--translate", action="store_true", help="translate speech to English")
    parser.add_argument("--output", type=Path, help="write here instead of standard output")
    parser.add_argument("--watch", type=Path, metavar="FOLDER", help="transcribe new recordings in FOLDER")
    parser.add_argument("--output-dir", type=Path, help="with --watch: where transcripts go (default: next to each file)")
    parser.add_argument("--interval", type=float, default=10.0, help="with --watch: seconds between scans")
    parser.add_argument("--remember", action="store_true", help="also add the transcript to memory")
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="with --format md: append an AI summary (sends the transcript to the configured AI provider)",
    )
    parser.add_argument(
        "--recorded-at",
        type=datetime.fromisoformat,
        help="with --remember: when the meeting took place (ISO time; default: file date)",
    )
    args = parser.parse_args()
    if (args.file is None) == (args.watch is None):
        parser.error("give a file, or --watch FOLDER (not both)")
    if args.summarize and args.format != "md":
        parser.error("--summarize needs --format md")
    if args.recorded_at is not None and args.recorded_at.tzinfo is None:
        args.recorded_at = args.recorded_at.astimezone()
    return args


def main() -> None:
    """Entry point of ``recall-transcribe``.

    Reads any audio or video file ffmpeg can decode and prints the transcript
    to standard output, or to ``--output``. ``--watch FOLDER`` instead keeps
    transcribing new recordings that appear there. Uses
    ``RECALL_WHISPER_MODEL``, ``RECALL_ASR_BACKEND``, ``RECALL_MODEL_DIR``
    and, for speaker names, ``HF_TOKEN``. Nothing leaves the machine unless
    ``--summarize`` is given, which sends the transcript to the AI provider
    set by ``RECALL_LLM_PROVIDER``; nothing is stored in memory unless
    ``--remember`` is given.
    """
    args = _parse_args()
    logging.basicConfig(level=logging.INFO if args.watch else logging.WARNING, format="%(levelname)s %(message)s")
    if args.file is not None and not args.file.is_file():
        sys.exit(f"No such file: {args.file}")
    if args.watch is not None and not args.watch.is_dir():
        sys.exit(f"No such folder: {args.watch}")
    try:
        settings = Settings.from_env(os.environ)
        remember = memory_writer(settings, args.recorded_at) if args.remember else None
        llm_settings = LlmSettings.from_env(os.environ) if args.summarize else None
        if args.summarize and llm_settings is None:
            raise LookupError("--summarize needs an AI model: set RECALL_LLM_PROVIDER (see .env.example).")
        llm = connect(llm_settings) if llm_settings is not None else None
        transcriber = load_transcriber(
            settings.asr_backend,
            settings.whisper_model,
            settings.model_dir,
            translate=args.translate,
            languages=settings.meeting_languages,
        )
    except (ValueError, LookupError, RuntimeError) as error:
        sys.exit(f"Invalid configuration: {error}")
    diarizer = None
    if settings.hf_token:
        try:
            diarizer = PyannoteDiarizer.from_pretrained(settings.hf_token, settings.model_dir)
        except RuntimeError as error:
            sys.stderr.write(f"{error} Continuing without speaker names.\n")

    def transcribe(path: Path) -> list[Segment]:
        return asyncio.run(transcribe_samples(decode_audio(path), transcriber, diarizer))

    def store(path: Path, segments: list[Segment]) -> None:
        if remember is None:
            return
        try:
            logger.info("Remembered %d segments of %s", remember(segments, path), path.name)
        except RuntimeError as error:
            raise RuntimeError(f"Memory is in use (is the engine running?): {error}") from error

    if args.watch is not None:
        def write(path: Path, segments: list[Segment]) -> None:
            store(path, segments)
            target = output_path(path, args.format, args.output_dir)
            text = render(segments, args.format, path)
            write_text(target, with_summary(text, llm) if llm is not None else text)
            logger.info("Transcribed %s -> %s", path.name, target)

        logger.info("Watching %s for new recordings (Ctrl+C to stop)", args.watch)
        try:
            watch(
                args.watch,
                transcribe,
                write,
                lambda path: output_path(path, args.format, args.output_dir).exists(),
                args.interval,
            )
        except KeyboardInterrupt:
            return
        return

    try:
        segments = transcribe(args.file)
        store(args.file, segments)
    except (av.FFmpegError, IndexError, ValueError) as error:
        sys.exit(f"Could not read audio from {args.file}: {error}")
    except RuntimeError as error:
        sys.exit(str(error))
    text = render(segments, args.format, args.file)
    if llm is not None:
        text = with_summary(text, llm)
    if args.output:
        write_text(args.output, text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
