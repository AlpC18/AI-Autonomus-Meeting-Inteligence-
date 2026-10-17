# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""After a meeting: its recording transcribed again with an accurate model.

Live captions need a fast model, which mishears words ("Büyükçe" for
"Bütçe"). After the meeting there is time for an accurate one.

The recording is not read in one piece: Whisper picks one language from the
first 30 seconds and keeps it, so a meeting that moves from Turkish to
German would come out wrong (in a test it kept only the last language).
Instead speech is found in the recording itself (the live model can miss
whole sentences in a language it handles badly), and each stretch between
pauses is read on its own, so each gets its own language: one person can
switch language, and without speaker separation every remote voice is the
same "others". Each stretch takes the speaker of the live line it overlaps
(or the nearest one).
"""

import multiprocessing
import wave
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from recall.audio.blocks import SAMPLE_RATE
from recall.audio.plausible import (
    MAX_COMPRESSION_RATIO,
    MIN_AVG_LOGPROB,
    compression_ratio,
    most_likely,
    phantom,
)
from recall.audio.transcriber import mlx_available, mlx_repo
from recall.live_controls import NOTE_SOURCE
from recall.transcript import Segment

MAX_PASSAGE_S = 25.0
"""Longer speech without a pause is cut, as Whisper reads 30-second windows."""

MIN_REGION_S = 1.5
"""Shorter speech is joined to a neighbour: Whisper cannot tell a language from half a word."""

MAX_JOIN_GAP_S = 1.0
"""Only speech this close to a short stretch is joined to it."""

PAD_S = 0.3
"""Audio kept on each side of a passage, so first and last words are whole."""

Line = tuple[float, float, str]
"""An accurate line: start and end in seconds on the recording's timeline, and its text."""


DEFAULT_VOICE = ("system", "others")
"""Source and speaker for speech when the live transcript has nothing at all."""


@dataclass(frozen=True, slots=True)
class Passage:
    """Consecutive speech of one speaker on the recording's timeline, and the live lines in it."""

    start: float
    end: float
    source: str
    speaker: str
    segments: tuple[Segment, ...]


@dataclass(frozen=True, slots=True)
class Polished:
    """A transcript line after polishing, with the live line it replaces (``None`` for notes)."""

    segment: Segment
    replaces: Segment | None


def speech_regions(audio: np.ndarray) -> list[tuple[float, float]]:
    """Where someone speaks in ``audio`` (16 kHz mono float32), in seconds."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    options = VadOptions(min_silence_duration_ms=500, speech_pad_ms=200, max_speech_duration_s=MAX_PASSAGE_S)
    found = [(span["start"] / SAMPLE_RATE, span["end"] / SAMPLE_RATE) for span in get_speech_timestamps(audio, options)]
    return join_short(found)


def join_short(regions: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Join each stretch shorter than :data:`MIN_REGION_S` to the closer neighbour within :data:`MAX_JOIN_GAP_S`."""
    joined = list(regions)
    changed = True
    while changed:
        changed = False
        for index, (start, end) in enumerate(joined):
            if end - start >= MIN_REGION_S:
                continue
            gaps = []
            if index > 0 and start - joined[index - 1][1] <= MAX_JOIN_GAP_S:
                gaps.append((start - joined[index - 1][1], index - 1))
            if index + 1 < len(joined) and joined[index + 1][0] - end <= MAX_JOIN_GAP_S:
                gaps.append((joined[index + 1][0] - end, index + 1))
            if not gaps:
                continue
            _, other = min(gaps)
            first, second = sorted((index, other))
            joined[first : second + 1] = [(joined[first][0], joined[second][1])]
            changed = True
            break
    return joined


def _on_recording(segment: Segment, offsets: Mapping[str, float]) -> tuple[float, float]:
    offset = offsets.get(segment.source, 0.0)
    return segment.start - offset, segment.end - offset


def _voice(start: float, end: float, spoken: Sequence[Segment], offsets: Mapping[str, float]) -> tuple[str, str]:
    """Source and speaker of the live line that overlaps ``start``-``end`` most, else the nearest one."""
    if not spoken:
        return DEFAULT_VOICE

    def closeness(segment: Segment) -> float:
        live_start, live_end = _on_recording(segment, offsets)
        return min(end, live_end) - max(start, live_start)  # negative: the gap between them

    best = max(spoken, key=closeness)
    return best.source, best.speaker


def passages(
    regions: Sequence[tuple[float, float]], live: Sequence[Segment], offsets: Mapping[str, float]
) -> list[Passage]:
    """One passage per speech region of the recording, with its speaker and the live lines in it.

    ``offsets`` holds, per source, how far into that source's stream the
    recording started.
    """
    # ponytail: one Whisper call per pause-separated stretch, so a language switch
    # is never decoded in the wrong language; merging stretches would be faster.
    spoken = [segment for segment in live if segment.source != NOTE_SOURCE]
    found = []
    for start, end in regions:
        source, speaker = _voice(start, end, spoken, offsets)
        inside = tuple(s for s in spoken if _overlap(_on_recording(s, offsets), (start, end)) > 0)
        found.append(Passage(start, end, source, speaker, inside))
    return found


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return min(a[1], b[1]) - max(a[0], b[0])


def polish_recording(
    path: Path,
    live: Sequence[Segment],
    offsets: Mapping[str, float],
    shown: Callable[[str], str],
    *,
    backend: str,
    model_size: str,
    model_dir: Path | None,
    languages: Sequence[str] = (),
) -> list["Polished"]:
    """The meeting's transcript read again from its recording. Blocks: minutes for a long meeting.

    ``languages`` are the codes of the languages spoken in the meeting; empty means any.
    """
    with wave.open(str(path), "rb") as recording:
        audio = np.frombuffer(recording.readframes(recording.getnframes()), dtype="<i2").astype(np.float32) / 32768
    found = passages(speech_regions(audio), live, offsets)
    lines = transcribe_passages(audio, [(p.start, p.end) for p in found], _reader(backend, model_size, model_dir, languages))
    return assemble(found, lines, live, offsets, shown)


@dataclass(frozen=True, slots=True)
class Reading:
    """What the model made of a stretch of audio, and how sure it was."""

    lines: list[Line]
    language: str | None
    confident: bool


Reader = Callable[[np.ndarray, str | None], Reading]
"""Transcribes audio, in the given language or (``None``) whatever it detects."""

def confident(parts: Sequence[tuple[str, float, float]]) -> bool:
    """Whether ``(text, avg_logprob, compression_ratio)`` parts look like real words, not invented noise."""
    if not parts:
        return True
    words = [text for text, _, _ in parts if len(text.strip()) > 2]
    if len(words) < len(parts) / 2:
        return False  # mostly stray letters and commas
    mean_logprob = sum(logprob for _, logprob, _ in parts) / len(parts)
    # The ratio is measured here too: the one the model reports let a repetition loop through.
    worst = max(max(ratio, compression_ratio(text)) for text, _, ratio in parts)
    return mean_logprob >= MIN_AVG_LOGPROB and worst <= MAX_COMPRESSION_RATIO


def transcribe_passages(audio: np.ndarray, spans: Sequence[tuple[float, float]], read: Reader) -> list[list[Line]]:
    """Transcribe each span of ``audio``; lines are on the recording's timeline.

    A stretch the model is unsure of is read again in the language of the
    stretch before it (people seldom switch mid-flow); if that is no better,
    it comes back empty so the live lines are kept instead of invented words.
    """
    results: list[list[Line]] = []
    language: str | None = None
    for start, end in spans:
        first = max(0, int((start - PAD_S) * SAMPLE_RATE))
        last = min(audio.size, int((end + PAD_S) * SAMPLE_RATE))
        if last <= first:
            results.append([])
            continue
        samples = audio[first:last]
        _wait_turn()
        reading = read(samples, None)
        if not reading.confident and language is not None and language != reading.language:
            _wait_turn()
            reading = read(samples, language)
        if reading.confident:
            language = reading.language or language
        offset = first / SAMPLE_RATE
        results.append([(s + offset, e + offset, text) for s, e, text in reading.lines] if reading.confident else [])
    return results


def _reader(backend: str, model_size: str, model_dir: Path | None, languages: Sequence[str] = ()) -> Reader:
    """Load ``model_size`` once and return a function that reads a stretch of audio.

    With ``languages``, a stretch is read in the most likely of them: on short
    stretches the model mistakes a less common language for another (Albanian
    for Russian or English) and then writes nonsense or translates.
    """
    cache = str(model_dir) if model_dir else None
    if backend == "mlx" or (backend == "auto" and mlx_available()):
        import mlx_whisper
        from huggingface_hub import snapshot_download

        repo = snapshot_download(mlx_repo(model_size), cache_dir=cache)

        def detect_mlx(samples: np.ndarray) -> str | None:
            if not languages:
                return None
            import mlx.core as mx
            from mlx_whisper.audio import log_mel_spectrogram, pad_or_trim
            from mlx_whisper.decoding import detect_language
            from mlx_whisper.transcribe import ModelHolder

            model = ModelHolder.get_model(repo, mx.float16)
            mel = log_mel_spectrogram(pad_or_trim(mx.array(samples)), n_mels=model.dims.n_mels)
            _tokens, probabilities = detect_language(model, mel.astype(mx.float16))
            # One clip gives one dict; a batch gives a list of them.
            ranked = probabilities if isinstance(probabilities, dict) else probabilities[0]
            return most_likely(ranked, languages)

        def read_mlx(samples: np.ndarray, language: str | None) -> Reading:
            language = language or detect_mlx(samples)
            result = mlx_whisper.transcribe(
                samples, path_or_hf_repo=repo, language=language, condition_on_previous_text=False, verbose=None
            )
            parts = result["segments"]
            return Reading(
                _clean((part["start"], part["end"], part["text"]) for part in parts),
                result.get("language"),
                confident([(p["text"], p["avg_logprob"], p["compression_ratio"]) for p in parts]),
            )

        return read_mlx
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="auto", compute_type="default", download_root=cache)

    def read_faster(samples: np.ndarray, language: str | None) -> Reading:
        if language is None and languages:
            _best, _probability, ranked = model.detect_language(samples)
            language = most_likely(dict(ranked), languages)
        found, info = model.transcribe(samples, language=language, condition_on_previous_text=False)
        parts = list(found)
        return Reading(
            _clean((part.start, part.end, part.text) for part in parts),
            info.language,
            confident([(p.text, p.avg_logprob, p.compression_ratio) for p in parts]),
        )

    return read_faster


def _clean(raw) -> list[Line]:
    return [(float(start), float(end), text.strip()) for start, end, text in raw if text.strip() and not phantom(text)]


def assemble(
    found: Sequence[Passage],
    lines: Sequence[Sequence[Line]],
    live: Sequence[Segment],
    offsets: Mapping[str, float],
    shown: Callable[[str], str] = lambda label: label,
) -> list[Polished]:
    """The polished transcript: each passage's accurate lines, with the passage's speaker.

    A passage that came back empty keeps its live lines, so nothing said is
    lost; speech the live transcript missed is added. ``shown`` turns a speaker label into the name the user gave it.
    The user's own notes are kept as they are.
    """
    result: list[Polished] = []
    for passage, passage_lines in zip(found, lines, strict=True):
        offset = offsets.get(passage.source, 0.0)
        if not passage_lines:
            result += [Polished(segment, segment) for segment in passage.segments]
            continue
        for start, end, text in passage_lines:
            # The live line it overlaps most, so a line flagged by the fact check stays flagged.
            def overlap(segment: Segment, start: float = start, end: float = end, offset: float = offset) -> float:
                return min(end + offset, segment.end) - max(start + offset, segment.start)

            best = max(passage.segments, key=overlap, default=None)
            replaces = best if best is not None and overlap(best) > 0 else None
            segment = Segment(passage.source, start + offset, end + offset, text, (), shown(passage.speaker))
            result.append(Polished(segment, replaces))
    result += [Polished(segment, None) for segment in live if segment.source == NOTE_SOURCE]
    return sorted(result, key=lambda polished: polished.segment.start)


# Set in the worker process: clear while the live engine is transcribing.
_live_idle: Any = None


def _use_gate(gate: Any) -> None:
    global _live_idle
    _live_idle = gate


def _wait_turn() -> None:
    """Let live captions go first: both models share one GPU, and live audio must not wait."""
    if _live_idle is not None:
        _live_idle.wait()


def in_own_process[**P, R](function: Callable[P, R], live_idle: Any = None) -> Callable[P, R]:
    """Run each call of ``function`` in a fresh process, giving way to live transcription.

    ``live_idle`` is a ``multiprocessing`` event of the spawn context that is
    set whenever the live engine is not transcribing; each stretch waits for
    it. Without that, live audio was dropped while polishing (500 blocks in a
    test): the accurate model kept the GPU busy and the live model waited.
    """

    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(1, mp_context=context, initializer=_use_gate, initargs=(live_idle,)) as pool:
            return pool.submit(function, *args, **kwargs).result()

    return run
