# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Engine settings, read from environment variables."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from continuum.audio.transcriber import BACKENDS
from continuum.memory.scope import TenantScope

KNOWN_SOURCES = ("mic", "system")
"""Audio sources the engine can capture."""

_PROPOSAL_TARGET = re.compile(r"calendar|slack|email|notion|jira:[A-Z][A-Z0-9_]{1,9}|github:[\w.-]+/[\w.-]+")


def _flag(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    value = env.get(name, "").strip().lower()
    if not value:
        return default
    return value not in {"0", "false", "off", "no"}


def _minutes(env: Mapping[str, str], name: str) -> int | None:
    raw = env.get(name, "").strip()
    if not raw:
        return None
    if not raw.isdecimal() or int(raw) < 1:
        raise ValueError(f"{name} must be a whole number of minutes, got {raw!r}")
    return int(raw)


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
    ``redact`` hides personal data and secrets in what is stored (memory and
    notes). ``retention_days`` deletes memories older than that many days
    each time the engine starts. When a meeting ends, its summary's action
    items are proposed to ``auto_propose`` targets (``calendar``, ``slack``, ``email``, ``notion``,
    ``jira:KEY``, ``github:owner/name``). ``idle_end_minutes`` ends a meeting
    after that long without speech; ``exit_when_idle`` then stops the engine
    (used by the app's auto-start). ``record_audio`` saves each meeting's
    audio next to its notes. ``llm_fact_check`` also asks the AI model about
    contradictions that involve no numbers. ``live_action_items`` shows the
    action items said so far during the meeting (an AI call at most every
    three minutes). ``require_disk_encryption`` stores nothing unless
    FileVault is on. ``remember_voices`` keeps the
    voices of speakers the user named, so later meetings show their names.
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
    redact: bool = True
    retention_days: int | None = None
    auto_propose: tuple[str, ...] = ()
    idle_end_minutes: int | None = None
    exit_when_idle: bool = False
    record_audio: bool = False
    llm_fact_check: bool = False
    live_action_items: bool = False
    require_disk_encryption: bool = False
    remember_voices: bool = True

    @property
    def voices_file(self) -> Path:
        """Where named voices are kept: next to the memory folder."""
        return self.memory_dir.parent / "voices.json"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        """Read settings from ``env`` (normally ``os.environ``).

        Variables: ``CONTINUUM_SOURCES`` (comma-separated, from ``mic`` and
        ``system``), ``CONTINUUM_WS_PORT``, ``CONTINUUM_WHISPER_MODEL``,
        ``CONTINUUM_MODEL_DIR``, ``HF_TOKEN``, ``CONTINUUM_TENANT_ID`` and
        ``CONTINUUM_PROJECT_ID`` (set both or neither), ``CONTINUUM_MEMORY_DIR``,
        ``CONTINUUM_EMBEDDING_MODEL``, ``CONTINUUM_NOTES_DIR``,
        ``CONTINUUM_ASR_BACKEND`` (``auto``, ``faster-whisper`` or ``mlx``),
        ``CONTINUUM_REDACT`` (``0`` turns redaction off), ``CONTINUUM_RETENTION_DAYS``,
        ``CONTINUUM_AUTO_PROPOSE`` (comma-separated), ``CONTINUUM_IDLE_END_MINUTES``,
        ``CONTINUUM_EXIT_WHEN_IDLE``, ``CONTINUUM_RECORD_AUDIO``,
        ``CONTINUUM_LLM_FACT_CHECK``, ``CONTINUUM_LIVE_ACTION_ITEMS``, ``CONTINUUM_REQUIRE_DISK_ENCRYPTION``, ``CONTINUUM_REMEMBER_VOICES`` (``0`` turns
        it off). Unset variables
        use defaults.

        Raises:
            ValueError: naming the offending variable, if a source is unknown,
                no source is given, the port is not a number in 1-65535, only
                one of tenant and project is set, either ID is malformed, or the
                speech backend is unknown, or the retention is not a positive
                number of days, a proposal target is malformed, or the idle
                time is not a positive number of minutes.
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

        raw_retention = env.get("CONTINUUM_RETENTION_DAYS", "").strip()
        if raw_retention and (not raw_retention.isdecimal() or int(raw_retention) < 1):
            raise ValueError(
                f"CONTINUUM_RETENTION_DAYS must be a whole number of days, got {raw_retention!r}"
            )
        redact = _flag(env, "CONTINUUM_REDACT", default=True)
        auto_propose = tuple(
            part.strip() for part in env.get("CONTINUUM_AUTO_PROPOSE", "").split(",") if part.strip()
        )
        bad_targets = [target for target in auto_propose if not _PROPOSAL_TARGET.fullmatch(target)]
        if bad_targets:
            raise ValueError(
                "CONTINUUM_AUTO_PROPOSE takes calendar, slack, email, jira:PROJECT or github:owner/name, "
                f"got {bad_targets[0]!r}"
            )
        idle_end_minutes = _minutes(env, "CONTINUUM_IDLE_END_MINUTES")

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
            redact=redact,
            retention_days=int(raw_retention) if raw_retention else None,
            auto_propose=auto_propose,
            idle_end_minutes=idle_end_minutes,
            exit_when_idle=_flag(env, "CONTINUUM_EXIT_WHEN_IDLE"),
            record_audio=_flag(env, "CONTINUUM_RECORD_AUDIO"),
            llm_fact_check=_flag(env, "CONTINUUM_LLM_FACT_CHECK"),
            live_action_items=_flag(env, "CONTINUUM_LIVE_ACTION_ITEMS"),
            require_disk_encryption=_flag(env, "CONTINUUM_REQUIRE_DISK_ENCRYPTION"),
            remember_voices=_flag(env, "CONTINUUM_REMEMBER_VOICES", default=True),
        )
