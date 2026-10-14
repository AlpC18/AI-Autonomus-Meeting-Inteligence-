# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Engine settings, read from environment variables."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from continuum.audio.transcriber import BACKENDS
from continuum.memory.scope import TenantScope

KNOWN_SOURCES = ("mic", "system")
"""Audio sources the engine can capture."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration of the engine.

    Build it with :meth:`from_env`. ``hf_token`` enables pyannote speaker
    separation; without it speakers are labelled by audio source only.
    ``scope`` enables memory: without it nothing is stored, because data must
    never be saved without knowing which tenant and project own it.
    ``notes_dir`` enables Markdown notes: each meeting's transcript is also
    written there as a plain file. ``asr_backend`` picks the speech model
    runtime: ``auto`` uses the Apple Silicon GPU (mlx) when available.
    """

    sources: tuple[str, ...] = KNOWN_SOURCES
    ws_port: int = 8765
    whisper_model: str = "base"
    model_dir: Path | None = None
    hf_token: str | None = None
    scope: TenantScope | None = None
    memory_dir: Path = Path.home() / ".continuum" / "memory"
    embedding_model: str | None = None
    notes_dir: Path | None = None
    asr_backend: str = "auto"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        """Read settings from ``env`` (normally ``os.environ``).

        Variables: ``CONTINUUM_SOURCES`` (comma-separated, from ``mic`` and
        ``system``), ``CONTINUUM_WS_PORT``, ``CONTINUUM_WHISPER_MODEL``,
        ``CONTINUUM_MODEL_DIR``, ``HF_TOKEN``, ``CONTINUUM_TENANT_ID`` and
        ``CONTINUUM_PROJECT_ID`` (set both or neither), ``CONTINUUM_MEMORY_DIR``,
        ``CONTINUUM_EMBEDDING_MODEL``, ``CONTINUUM_NOTES_DIR``,
        ``CONTINUUM_ASR_BACKEND`` (``auto``, ``faster-whisper`` or ``mlx``). Unset variables
        use defaults.

        Raises:
            ValueError: naming the offending variable, if a source is unknown,
                no source is given, the port is not a number in 1-65535, only
                one of tenant and project is set, either ID is malformed, or the
                speech backend is unknown.
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

        tenant_id = env.get("CONTINUUM_TENANT_ID")
        project_id = env.get("CONTINUUM_PROJECT_ID")
        scope = None
        if tenant_id or project_id:
            if not (tenant_id and project_id):
                raise ValueError(
                    "CONTINUUM_TENANT_ID and CONTINUUM_PROJECT_ID must be set together"
                )
            try:
                scope = TenantScope(tenant_id, project_id)
            except ValueError as error:
                raise ValueError(f"CONTINUUM_TENANT_ID / CONTINUUM_PROJECT_ID: {error}") from error

        asr_backend = env.get("CONTINUUM_ASR_BACKEND", "").strip().lower() or defaults.asr_backend
        if asr_backend not in BACKENDS:
            raise ValueError(f"CONTINUUM_ASR_BACKEND must be one of {BACKENDS}, got {asr_backend!r}")


        model_dir = env.get("CONTINUUM_MODEL_DIR")
        memory_dir = env.get("CONTINUUM_MEMORY_DIR")
        notes_dir = env.get("CONTINUUM_NOTES_DIR")
        return cls(
            sources=sources,
            ws_port=int(raw_port),
            whisper_model=env.get("CONTINUUM_WHISPER_MODEL") or defaults.whisper_model,
            model_dir=Path(model_dir) if model_dir else None,
            hf_token=env.get("HF_TOKEN") or None,
            scope=scope,
            memory_dir=Path(memory_dir) if memory_dir else defaults.memory_dir,
            embedding_model=env.get("CONTINUUM_EMBEDDING_MODEL") or None,
            notes_dir=Path(notes_dir).expanduser() if notes_dir else None,
            asr_backend=asr_backend,
        )
