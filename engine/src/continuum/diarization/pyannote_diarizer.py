# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Separates the speakers inside an utterance with pyannote.audio."""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import numpy as np

from continuum.audio.blocks import SAMPLE_RATE
from continuum.audio.chunker import Utterance
from continuum.diarization.tracker import SpeakerTracker
from continuum.diarization.turns import SpeakerTurn
from continuum.diarization.voices import VoiceBook

MODEL = "pyannote/speaker-diarization-community-1"
"""Gated Hugging Face pipeline; its terms must be accepted for the token used."""

MIN_EMBED_S = 0.25
"""Speech shorter than this is not sent to the voice model at all."""


class PyannoteDiarizer:
    """Finds who speaks when in one audio stream, utterance by utterance.

    Build with :meth:`from_pretrained` and use one instance per stream: it
    remembers the voices it has heard, so a speaker keeps the same name
    ("Speaker 1", "Speaker 2", ...) from one utterance to the next.
    :meth:`diarize` blocks while the models run; call it from a worker thread,
    one call at a time.
    """

    # ponytail: the pipeline only sees one utterance (15 s at most), and with
    # so little audio it often hears two people as one. Such an utterance gets
    # a single name. Giving the model a longer window fixes that but cost
    # about 0.9 s of CPU per second of window on an M1, too slow to run live.
    def __init__(
        self,
        pipeline: Callable[[Mapping[str, Any]], Any],
        embed: Callable[[np.ndarray], np.ndarray],
        voices: VoiceBook | None = None,
    ) -> None:
        """``pipeline`` splits audio into turns with labels that are only
        valid for that one call. ``embed`` turns one speaker's mono samples
        into a voice embedding, which is what links the calls together.
        ``voices``, when given, recognises people named in earlier meetings."""
        self._pipeline = pipeline
        self._embed = embed
        self._tracker = SpeakerTracker()
        self._voices = voices

    @classmethod
    def from_pretrained(
        cls, token: str, cache_dir: Path | None = None, voices: VoiceBook | None = None
    ) -> "PyannoteDiarizer":
        """Load the pyannote pipeline, downloading it on first use.

        Raises:
            RuntimeError: if the ``diarization`` extra is not installed, or
                the model cannot be loaded (invalid token, or the model's
                terms were not accepted on huggingface.co).
        """
        try:
            from pyannote.audio import Pipeline
        except ImportError as error:
            raise RuntimeError(
                "Speaker separation needs the 'diarization' extra: "
                "run `uv sync --extra diarization`."
            ) from error
        try:
            pipeline = Pipeline.from_pretrained(MODEL, token=token, cache_dir=cache_dir)
        except Exception as error:
            raise RuntimeError(
                f"Could not load {MODEL}. Check HF_TOKEN and that you accepted the "
                f"model's terms at https://huggingface.co/{MODEL}."
            ) from error
        if pipeline is None:
            raise RuntimeError(f"Could not load {MODEL}: the download returned nothing.")

        import torch

        def embed(samples: np.ndarray) -> np.ndarray:
            # The pipeline's own voice model; it has no public accessor.
            return pipeline._embedding(torch.from_numpy(samples)[None, None])[0]

        return cls(pipeline, embed, voices)

    def speaker_merges(self) -> dict[str, str]:
        """Duplicate speakers found by comparing final voices; see :meth:`SpeakerTracker.merges`."""
        return self._tracker.merges()

    def recognise(self, label: str) -> str | None:
        """The remembered name of the person speaking as ``label``, if their voice is known."""
        voice = self._tracker.voice(label)
        if self._voices is None or voice is None:
            return None
        return self._voices.identify(voice)

    def learn(self, label: str, name: str) -> None:
        """Remember the voice of ``label`` as ``name`` for later meetings.

        Raises:
            OSError: if the remembered voices cannot be saved.
        """
        voice = self._tracker.voice(label)
        if self._voices is not None and voice is not None:
            self._voices.learn(name, voice)

    def reset(self) -> None:
        """Forget this meeting's voices: the next meeting starts again at "Speaker 1".

        Voices remembered by name are kept."""
        self._tracker = SpeakerTracker()

    def diarize(self, utterance: Utterance) -> list[SpeakerTurn]:
        """Return the speaker turns in ``utterance`` on the stream timeline.

        Turns never overlap each other and carry session-wide speaker names.
        Speech too short to recognise a voice from is left out, as is
        everything when the model hears no speech.
        """
        import torch

        waveform = torch.from_numpy(utterance.samples).unsqueeze(0)
        output = self._pipeline({"waveform": waveform, "sample_rate": SAMPLE_RATE})
        turns = [
            (turn.start, turn.end, str(label))
            for turn, _track, label in output.exclusive_speaker_diarization.itertracks(
                yield_label=True
            )
        ]

        names: dict[str, str | None] = {}
        for label in dict.fromkeys(label for _start, _end, label in turns):
            samples = np.concatenate(
                [
                    utterance.samples[int(start * SAMPLE_RATE) : int(end * SAMPLE_RATE)]
                    for start, end, turn_label in turns
                    if turn_label == label
                ]
            )
            seconds = len(samples) / SAMPLE_RATE
            names[label] = (
                self._tracker.name(self._embed(samples), seconds)
                if seconds >= MIN_EMBED_S
                else None
            )

        offset = utterance.start_s
        return [
            SpeakerTurn(offset + start, offset + end, name)
            for start, end, label in turns
            if (name := names[label]) is not None
        ]
