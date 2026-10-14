# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Transcribes a recording from disk, with the same models as live capture."""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import av
import numpy as np

from continuum.audio.blocks import SAMPLE_RATE
from continuum.audio.transcriber import SpeechToText, load_transcriber
from continuum.config import Settings
from continuum.diarization.pyannote_diarizer import PyannoteDiarizer
from continuum.notes import markdown_lines, speaker_runs, srt
from continuum.pipeline import Engine
from continuum.transcript import Segment

_BLOCK = SAMPLE_RATE // 10


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


def render(segments: list[Segment], fmt: str) -> str:
    """Format ``segments`` as ``md`` (Markdown), ``srt`` (subtitles) or ``txt``."""
    if fmt == "srt":
        return srt(segments)
    if fmt == "txt":
        return "".join(
            f"{speaker}: {text}\n"
            for segment in segments
            for speaker, _start, text in speaker_runs(segment)
        )
    return "".join(line + "\n" for segment in segments for line in markdown_lines(segment))


def main() -> None:
    """Entry point of ``continuum-transcribe``.

    Reads any audio or video file ffmpeg can decode and prints the transcript
    to standard output, or to ``--output``. Uses ``CONTINUUM_WHISPER_MODEL``,
    ``CONTINUUM_MODEL_DIR`` and, for speaker names, ``HF_TOKEN``. Nothing is
    stored in memory and nothing leaves the machine.
    """
    parser = argparse.ArgumentParser(description="Transcribe an audio or video file.")
    parser.add_argument("file", type=Path, help="recording to transcribe")
    parser.add_argument("--format", choices=("md", "srt", "txt"), default="md")
    parser.add_argument("--translate", action="store_true", help="translate speech to English")
    parser.add_argument("--output", type=Path, help="write here instead of standard output")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    if not args.file.is_file():
        sys.exit(f"No such file: {args.file}")
    try:
        settings = Settings.from_env(os.environ)
    except ValueError as error:
        sys.exit(f"Invalid configuration: {error}")

    try:
        samples = decode_audio(args.file)
    except (av.FFmpegError, IndexError, ValueError) as error:
        sys.exit(f"Could not read audio from {args.file}: {error}")

    try:
        transcriber = load_transcriber(
            settings.asr_backend, settings.whisper_model, settings.model_dir, translate=args.translate
        )
    except RuntimeError as error:
        sys.exit(str(error))
    diarizer = None
    if settings.hf_token:
        try:
            diarizer = PyannoteDiarizer.from_pretrained(settings.hf_token, settings.model_dir)
        except RuntimeError as error:
            sys.stderr.write(f"{error} Continuing without speaker names.\n")

    text = render(asyncio.run(transcribe_samples(samples, transcriber, diarizer)), args.format)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
