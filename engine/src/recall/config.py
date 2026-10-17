# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Engine settings, read from environment variables."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from recall.audio.transcriber import BACKENDS
from recall.memory.scope import TenantScope
from recall.templates import CHOICES as TEMPLATE_CHOICES
from recall.translate import TARGETS as TRANSLATION_TARGETS

KNOWN_SOURCES = ("mic", "system", "tab")
"""Audio sources the engine can capture; ``tab`` is a browser tab sent by the extension."""

DEFAULT_SOURCES = ("mic", "system")

_PROPOSAL_TARGET = re.compile(r"calendar|slack|email|notion|jira:[A-Z][A-Z0-9_]{1,9}|github:[\w.-]+/[\w.-]+|gitlab:[\w.-]+(?:/[\w.-]+)+")


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
    ``jira:KEY``, ``github:owner/name``, ``gitlab:group/name``). ``idle_end_minutes`` ends a meeting
    after that long without speech; ``exit_when_idle`` then stops the engine
    (used by the app's auto-start). ``record_audio`` saves each meeting's
    audio next to its notes. ``final_model`` transcribes the meeting's audio
    again after it ends, for accurate notes, memory and summary (kept only
    while that runs unless ``record_audio`` is on); ``None`` keeps the live text. ``llm_hesitations`` has the AI model read the transcript at
    the end for doubts the phrase list missed. ``llm_fact_check`` also asks the AI model about
    contradictions that involve no numbers. ``live_action_items`` shows the
    action items said so far during the meeting (an AI call at most every
    three minutes). ``require_disk_encryption`` stores nothing unless
    FileVault is on. ``remember_voices`` keeps the
    voices of speakers the user named, so later meetings show their names.
    ``code_dirs`` are local checkouts indexed for code context hints.
    ``risk_tracking`` lists dated promises and moments of doubt in the notes;
    ``workload_check`` also counts the speaker's open Jira and GitHub issues and warns
    when a promised date looks unrealistic. ``meeting_apps_only`` captures
    system audio only from meeting apps and browsers (macOS).
    ``browser_tab_audio`` takes calls in a browser from the browser extension,
    which sends only the meeting tab, and leaves browsers out of system audio;
    ``browser_extension_id`` limits that to one installed extension.
    ``extra_meeting_apps`` are bundle IDs of further meeting apps to hear.
    ``translate_to`` shows a live translation of every line in that language
    (sent to the AI provider). ``screen_fact_check`` also checks the figures on
    shared slides, read on this computer from the meeting window (macOS).
    """

    sources: tuple[str, ...] = DEFAULT_SOURCES
    ws_port: int = 8765
    whisper_model: str = "small"
    model_dir: Path | None = None
    hf_token: str | None = None
    scope: TenantScope | None = None
    memory_dir: Path = Path.home() / ".recall" / "memory"
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
    llm_hesitations: bool = False
    live_action_items: bool = False
    require_disk_encryption: bool = False
    remember_voices: bool = True
    code_dirs: tuple[Path, ...] = ()
    risk_tracking: bool = True
    workload_check: bool = False
    meeting_apps_only: bool = False
    browser_tab_audio: bool = False
    browser_extension_id: str | None = None
    extra_meeting_apps: frozenset[str] = frozenset()
    translate_to: str | None = None
    screen_fact_check: bool = False
    meeting_template: str = "auto"

    @property
    def voices_file(self) -> Path:
        """Where named voices are kept: next to the memory folder."""
        return self.memory_dir.parent / "voices.json"

    final_model: str | None = "large-v3-turbo"
    meeting_languages: tuple[str, ...] = ()
    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        """Read settings from ``env`` (normally ``os.environ``).

        Variables: ``RECALL_SOURCES`` (comma-separated, from ``mic`` and
        ``system``), ``RECALL_WS_PORT``, ``RECALL_WHISPER_MODEL``, ``RECALL_FINAL_MODEL`` (the model that
        transcribes the recording again after the meeting; ``off`` keeps the live text),
        ``RECALL_MEETING_LANGUAGES`` (comma-separated codes such as ``en,tr,de,it,sq``: the after-meeting
        transcript only chooses among them),
        ``RECALL_MODEL_DIR``, ``HF_TOKEN``, ``RECALL_TENANT_ID`` and
        ``RECALL_PROJECT_ID`` (set both or neither), ``RECALL_MEMORY_DIR``,
        ``RECALL_EMBEDDING_MODEL``, ``RECALL_NOTES_DIR``,
        ``RECALL_ASR_BACKEND`` (``auto``, ``faster-whisper`` or ``mlx``),
        ``RECALL_REDACT`` (``0`` turns redaction off), ``RECALL_RETENTION_DAYS``,
        ``RECALL_AUTO_PROPOSE`` (comma-separated), ``RECALL_IDLE_END_MINUTES``,
        ``RECALL_EXIT_WHEN_IDLE``, ``RECALL_RECORD_AUDIO``,
        ``RECALL_LLM_FACT_CHECK``, ``RECALL_LLM_HESITATIONS``, ``RECALL_LIVE_ACTION_ITEMS``, ``RECALL_REQUIRE_DISK_ENCRYPTION``, ``RECALL_REMEMBER_VOICES`` (``0`` turns
        it off), ``RECALL_CODE_DIRS`` (comma-separated folders),
        ``RECALL_RISK_TRACKING`` (``0`` turns it off), ``RECALL_WORKLOAD_CHECK``,
        ``RECALL_MEETING_APPS_ONLY``, ``RECALL_BROWSER_TAB_AUDIO`` (adds the
        ``tab`` source), ``RECALL_BROWSER_EXTENSION_ID``, ``RECALL_MEETING_APPS`` (comma-separated
        bundle IDs; ``*`` at the end matches a prefix), ``RECALL_LANGUAGE`` (``en`` or
        ``tr``: notes, hints and AI replies; read by :mod:`recall.language`),
        ``RECALL_TRANSLATE_TO`` (a code from :data:`recall.translate.TARGETS`),
        ``RECALL_SCREEN_FACT_CHECK``, ``RECALL_MEETING_TEMPLATE`` (see
        :data:`recall.templates.CHOICES`). Unset variables
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
        raw_sources = env.get("RECALL_SOURCES")
        sources = defaults.sources
        if raw_sources is not None:
            sources = tuple(part.strip() for part in raw_sources.split(",") if part.strip())
            unknown = [source for source in sources if source not in KNOWN_SOURCES]
            if unknown or not sources:
                raise ValueError(
                    f"RECALL_SOURCES must list one or more of {KNOWN_SOURCES}, "
                    f"got {raw_sources!r}"
                )

        raw_port = env.get("RECALL_WS_PORT", str(defaults.ws_port))
        if not raw_port.isdecimal() or not 1 <= int(raw_port) <= 65535:
            raise ValueError(f"RECALL_WS_PORT must be a port number, got {raw_port!r}")

        tenant_id = env.get("RECALL_TENANT_ID")
        project_id = env.get("RECALL_PROJECT_ID")
        scope = None
        if tenant_id or project_id:
            if not (tenant_id and project_id):
                raise ValueError(
                    "RECALL_TENANT_ID and RECALL_PROJECT_ID must be set together"
                )
            try:
                scope = TenantScope(tenant_id, project_id)
            except ValueError as error:
                raise ValueError(f"RECALL_TENANT_ID / RECALL_PROJECT_ID: {error}") from error

        asr_backend = env.get("RECALL_ASR_BACKEND", "").strip().lower() or defaults.asr_backend
        if asr_backend not in BACKENDS:
            raise ValueError(f"RECALL_ASR_BACKEND must be one of {BACKENDS}, got {asr_backend!r}")

        raw_retention = env.get("RECALL_RETENTION_DAYS", "").strip()
        if raw_retention and (not raw_retention.isdecimal() or int(raw_retention) < 1):
            raise ValueError(
                f"RECALL_RETENTION_DAYS must be a whole number of days, got {raw_retention!r}"
            )
        redact = _flag(env, "RECALL_REDACT", default=True)
        auto_propose = tuple(
            part.strip() for part in env.get("RECALL_AUTO_PROPOSE", "").split(",") if part.strip()
        )
        bad_targets = [target for target in auto_propose if not _PROPOSAL_TARGET.fullmatch(target)]
        if bad_targets:
            raise ValueError(
                "RECALL_AUTO_PROPOSE takes calendar, slack, email, notion, jira:PROJECT, github:owner/name "
                "or gitlab:group/name, "
                f"got {bad_targets[0]!r}"
            )
        idle_end_minutes = _minutes(env, "RECALL_IDLE_END_MINUTES")

        code_dirs = tuple(
            Path(part.strip()).expanduser()
            for part in env.get("RECALL_CODE_DIRS", "").split(",")
            if part.strip()
        )
        missing = [str(path) for path in code_dirs if not path.is_dir()]
        if missing:
            raise ValueError(f"RECALL_CODE_DIRS: not a folder: {missing[0]!r}")

        browser_tab_audio = _flag(env, "RECALL_BROWSER_TAB_AUDIO")
        if browser_tab_audio and "tab" not in sources:
            sources = (*sources, "tab")
        extension_id = env.get("RECALL_BROWSER_EXTENSION_ID", "").strip() or None
        if extension_id is not None and not re.fullmatch(
            r"[a-p]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", extension_id
        ):
            raise ValueError(
                "RECALL_BROWSER_EXTENSION_ID must be the 32-letter ID shown in chrome://extensions "
                f"or the Firefox UUID shown in about:debugging, got {extension_id!r}"
            )

        language = env.get("RECALL_LANGUAGE", "").strip().lower() or "en"
        if language not in ("en", "tr"):
            raise ValueError(f"RECALL_LANGUAGE must be en or tr, got {language!r}")

        translate_to = env.get("RECALL_TRANSLATE_TO", "").strip().lower() or None
        if translate_to is not None and translate_to not in TRANSLATION_TARGETS:
            raise ValueError(
                f"RECALL_TRANSLATE_TO must be one of {', '.join(sorted(TRANSLATION_TARGETS))}, got {translate_to!r}"
            )

        meeting_template = env.get("RECALL_MEETING_TEMPLATE", "").strip().lower() or "auto"
        if meeting_template not in TEMPLATE_CHOICES:
            raise ValueError(
                f"RECALL_MEETING_TEMPLATE must be one of {', '.join(TEMPLATE_CHOICES)}, got {meeting_template!r}"
            )

        extra_apps = frozenset(
            part.strip() for part in env.get("RECALL_MEETING_APPS", "").split(",") if part.strip()
        )
        bad_apps = sorted(app for app in extra_apps if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,254}\*?", app))
        if bad_apps:
            raise ValueError(
                f"RECALL_MEETING_APPS takes bundle IDs like com.example.Meet, got {bad_apps[0]!r}"
            )

        model_dir = env.get("RECALL_MODEL_DIR")
        memory_dir = env.get("RECALL_MEMORY_DIR")
        notes_dir = env.get("RECALL_NOTES_DIR")
        return cls(
            sources=sources,
            ws_port=int(raw_port),
            whisper_model=env.get("RECALL_WHISPER_MODEL") or defaults.whisper_model,
            final_model=_final_model(env.get("RECALL_FINAL_MODEL"), defaults.final_model),
            meeting_languages=_language_codes(env.get("RECALL_MEETING_LANGUAGES", "")),
            model_dir=Path(model_dir) if model_dir else None,
            hf_token=env.get("HF_TOKEN") or None,
            scope=scope,
            memory_dir=Path(memory_dir) if memory_dir else defaults.memory_dir,
            embedding_model=env.get("RECALL_EMBEDDING_MODEL") or None,
            notes_dir=Path(notes_dir).expanduser() if notes_dir else None,
            asr_backend=asr_backend,
            redact=redact,
            retention_days=int(raw_retention) if raw_retention else None,
            auto_propose=auto_propose,
            idle_end_minutes=idle_end_minutes,
            exit_when_idle=_flag(env, "RECALL_EXIT_WHEN_IDLE"),
            record_audio=_flag(env, "RECALL_RECORD_AUDIO"),
            llm_fact_check=_flag(env, "RECALL_LLM_FACT_CHECK"),
            llm_hesitations=_flag(env, "RECALL_LLM_HESITATIONS"),
            live_action_items=_flag(env, "RECALL_LIVE_ACTION_ITEMS"),
            require_disk_encryption=_flag(env, "RECALL_REQUIRE_DISK_ENCRYPTION"),
            remember_voices=_flag(env, "RECALL_REMEMBER_VOICES", default=True),
            code_dirs=code_dirs,
            risk_tracking=_flag(env, "RECALL_RISK_TRACKING", default=True),
            workload_check=_flag(env, "RECALL_WORKLOAD_CHECK"),
            meeting_apps_only=_flag(env, "RECALL_MEETING_APPS_ONLY"),
            browser_tab_audio=browser_tab_audio,
            browser_extension_id=extension_id,
            extra_meeting_apps=extra_apps,
            translate_to=translate_to,
            screen_fact_check=_flag(env, "RECALL_SCREEN_FACT_CHECK"),
            meeting_template=meeting_template,
        )


def _final_model(raw: str | None, default: str | None) -> str | None:
    """The after-meeting model: unset means the default, ``off`` (or ``0``) means none."""
    value = (raw or "").strip()
    if not value:
        return default
    return None if value.lower() in {"off", "0", "none"} else value


def _language_codes(raw: str) -> tuple[str, ...]:
    """``"en, TR,sq"`` → ``("en", "tr", "sq")``.

    Raises:
        ValueError: on something that is not a two- or three-letter language code.
    """
    codes = tuple(code.strip().lower() for code in raw.split(",") if code.strip())
    for code in codes:
        if not (2 <= len(code) <= 3 and code.isalpha() and code.isascii()):
            raise ValueError(f"RECALL_MEETING_LANGUAGES: {code!r} is not a language code like en, tr or sq")
    return codes
