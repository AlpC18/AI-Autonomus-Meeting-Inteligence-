# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Separates the speakers inside an utterance with pyannote.audio."""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from continuum.audio.blocks import SAMPLE_RATE
from continuum.audio.chunker import Utterance
from continuum.diarization.turns import SpeakerTurn

MODEL = "pyannote/speaker-diarization-community-1"
"""Gated Hugging Face pipeline; its terms must be accepted for the token used."""


class PyannoteDiarizer:
    """Finds who speaks when within one utterance.

    Build with :meth:`from_pretrained`. :meth:`diarize` blocks while the model
    runs; call it from a worker thread, one call at a time.
    """

    # ponytail: speaker labels (SPEAKER_00, ...) are only consistent inside one
    # utterance, so "SPEAKER_00" in two utterances may be different people.
    # Stable identities across a meeting need the pipeline's speaker embeddings
    # matched against a per-session registry.
    def __init__(self, pipeline: Callable[[Mapping[str, Any]], Any]) -> None:
        self._pipeline = pipeline

    @classmethod
    def from_pretrained(cls, token: str, cache_dir: Path | None = None) -> "PyannoteDiarizer":
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
        return cls(pipeline)

    def diarize(self, utterance: Utterance) -> list[SpeakerTurn]:
        """Return the speaker turns in ``utterance`` on the stream timeline.

        Turns never overlap each other. Returns an empty list when the model
        hears no speech.
        """
        import torch

        waveform = torch.from_numpy(utterance.samples).unsqueeze(0)
        output = self._pipeline({"waveform": waveform, "sample_rate": SAMPLE_RATE})
        offset = utterance.start_s
        return [
            SpeakerTurn(offset + turn.start, offset + turn.end, str(speaker))
            for turn, _track, speaker in output.exclusive_speaker_diarization.itertracks(
                yield_label=True
            )
        ]
