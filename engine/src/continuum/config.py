# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Engine settings, read from environment variables."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

KNOWN_SOURCES = ("mic", "system")
"""Audio sources the engine can capture."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration of the engine.

    Build it with :meth:`from_env`. ``hf_token`` enables pyannote speaker
    separation; without it speakers are labelled by audio source only.
    """

    sources: tuple[str, ...] = KNOWN_SOURCES
    ws_port: int = 8765
    whisper_model: str = "base"
    model_dir: Path | None = None
    hf_token: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        """Read settings from ``env`` (normally ``os.environ``).

        Variables: ``CONTINUUM_SOURCES`` (comma-separated, from ``mic`` and
        ``system``), ``CONTINUUM_WS_PORT``, ``CONTINUUM_WHISPER_MODEL``,
        ``CONTINUUM_MODEL_DIR``, ``HF_TOKEN``. Unset variables use defaults.

        Raises:
            ValueError: naming the offending variable, if a source is unknown,
                no source is given, or the port is not a number in 1-65535.
        """
        defaults = cls()
        raw_sources = env.get("CONTINUUM_SOURCES")
        sources = defaults.sources
        if raw_sources is not None:
            sources = tuple(part.strip() for part in raw_sources.split(",") if part.strip())
            unknown = [source for source in sources if source not in KNOWN_SOURCES]
            if unknown or not sources:
                raise ValueError(
                    f"CONTINUUM_SOURCES must list one or more of {KNOWN_SOURCES}, "
                    f"got {raw_sources!r}"
                )

        raw_port = env.get("CONTINUUM_WS_PORT", str(defaults.ws_port))
        if not raw_port.isdecimal() or not 1 <= int(raw_port) <= 65535:
            raise ValueError(f"CONTINUUM_WS_PORT must be a port number, got {raw_port!r}")

        model_dir = env.get("CONTINUUM_MODEL_DIR")
        return cls(
            sources=sources,
            ws_port=int(raw_port),
            whisper_model=env.get("CONTINUUM_WHISPER_MODEL") or defaults.whisper_model,
            model_dir=Path(model_dir) if model_dir else None,
            hf_token=env.get("HF_TOKEN") or None,
        )
