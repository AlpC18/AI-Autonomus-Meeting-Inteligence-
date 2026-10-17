# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""After a meeting: its recording transcribed again with an accurate model.

Live captions need a fast model, which mishears words ("Büyükçe" for
"Bütçe"). After the meeting there is time for an accurate one.

The recording is not read in one piece: Whisper picks one language from the
first 30 seconds and keeps it, so a meeting that moves from Turkish to
German would come out wrong (in a test it kept only the last language).
Instead the live transcript says where each person spoke; consecutive
speech of one speaker is read as one passage of up to :data:`MAX_PASSAGE_S`,
each with its own language, and keeps that speaker.
"""

import wave
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from recall.audio.blocks import SAMPLE_RATE
from recall.audio.transcriber import mlx_available, mlx_repo
from recall.live_controls import NOTE_SOURCE
from recall.transcript import Segment

MAX_PASSAGE_S = 25.0
"""Whisper reads 30-second windows: passages close to that waste little work."""

MAX_GAP_S = 2.0
"""A longer pause starts a new passage."""

PAD_S = 0.3
"""Audio kept on each side of a passage, so first and last words are whole."""

Line = tuple[float, float, str]
"""An accurate line: start and end in seconds on the recording's timeline, and its text."""


@dataclass(frozen=True, slots=True)
class Passage:
    """Consecutive live segments of one speaker, with their span on the recording's timeline."""

    start: float
    end: float
    segments: tuple[Segment, ...]


@dataclass(frozen=True, slots=True)
class Polished:
    """A transcript line after polishing, with the live line it replaces (``None`` for notes)."""

    segment: Segment
    replaces: Segment | None


def passages(live: Sequence[Segment], offsets: Mapping[str, float]) -> list[Passage]:
    """Group the spoken ``live`` segments into passages to transcribe again.

    ``offsets`` holds, per source, how far into that source's stream the
    recording started; segments from before the recording are skipped.
    """
    spoken = sorted(
        (
            (segment.start - offsets.get(segment.source, 0.0), segment.end - offsets.get(segment.source, 0.0), segment)
            for segment in live
            if segment.source != NOTE_SOURCE
        ),
        key=lambda item: item[0],
    )
    found: list[Passage] = []
    for start, end, segment in spoken:
        if end <= 0:
            continue
        start = max(start, 0.0)
        last = found[-1] if found else None
        if (
            last is not None
            and segment.speaker == last.segments[-1].speaker
            and segment.source == last.segments[-1].source
            and start - last.end <= MAX_GAP_S
            and end - last.start <= MAX_PASSAGE_S
        ):
            found[-1] = Passage(last.start, max(last.end, end), (*last.segments, segment))
        else:
            found.append(Passage(start, end, (segment,)))
    return found


def transcribe_recording(
    path: Path, spans: Sequence[tuple[float, float]], backend: str, model_size: str, model_dir: Path | None
) -> list[list[Line]]:
    """Transcribe each span of the WAV at ``path``; lines are on the recording's timeline.

    Loads the model once. Blocks: minutes for a long meeting.
    """
    with wave.open(str(path), "rb") as recording:
        audio = np.frombuffer(recording.readframes(recording.getnframes()), dtype="<i2").astype(np.float32) / 32768
    read = _reader(backend, model_size, model_dir)
    results = []
    for start, end in spans:
        first = max(0, int((start - PAD_S) * SAMPLE_RATE))
        last = min(audio.size, int((end + PAD_S) * SAMPLE_RATE))
        offset = first / SAMPLE_RATE
        results.append([(s + offset, e + offset, text) for s, e, text in read(audio[first:last])] if last > first else [])
    return results


def _reader(backend: str, model_size: str, model_dir: Path | None) -> Callable[[np.ndarray], list[Line]]:
    """A function that transcribes a stretch of audio, in whatever language it is in."""
    cache = str(model_dir) if model_dir else None
    if backend == "mlx" or (backend == "auto" and mlx_available()):
        import mlx_whisper
        from huggingface_hub import snapshot_download

        repo = snapshot_download(mlx_repo(model_size), cache_dir=cache)

        def read_mlx(samples: np.ndarray) -> list[Line]:
            result = mlx_whisper.transcribe(samples, path_or_hf_repo=repo, condition_on_previous_text=False, verbose=None)
            return _clean((part["start"], part["end"], part["text"]) for part in result["segments"])

        return read_mlx
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="auto", compute_type="default", download_root=cache)

    def read_faster(samples: np.ndarray) -> list[Line]:
        parts, _info = model.transcribe(samples, condition_on_previous_text=False)
        return _clean((part.start, part.end, part.text) for part in parts)

    return read_faster


def _clean(raw) -> list[Line]:
    return [(float(start), float(end), text.strip()) for start, end, text in raw if text.strip()]


def assemble(
    found: Sequence[Passage],
    lines: Sequence[Sequence[Line]],
    live: Sequence[Segment],
    offsets: Mapping[str, float],
    shown: Callable[[str], str] = lambda label: label,
) -> list[Polished]:
    """The polished transcript: each passage's accurate lines, with the passage's speaker.

    A passage that came back empty keeps its live lines, so nothing said is
    lost. ``shown`` turns a speaker label into the name the user gave it.
    The user's own notes are kept as they are.
    """
    result: list[Polished] = []
    for passage, passage_lines in zip(found, lines, strict=True):
        first = passage.segments[0]
        offset = offsets.get(first.source, 0.0)
        if not passage_lines:
            result += [Polished(segment, segment) for segment in passage.segments]
            continue
        for start, end, text in passage_lines:
            # The live line it overlaps most, so a line flagged by the fact check stays flagged.
            replaces = max(
                passage.segments,
                key=lambda segment: min(end + offset, segment.end) - max(start + offset, segment.start),
            )
            segment = Segment(first.source, start + offset, end + offset, text, (), shown(first.speaker))
            result.append(Polished(segment, replaces))
    result += [Polished(segment, None) for segment in live if segment.source == NOTE_SOURCE]
    return sorted(result, key=lambda polished: polished.segment.start)
