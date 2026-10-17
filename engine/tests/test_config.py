# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Settings parsing: defaults, overrides, and rejection of bad values."""

from pathlib import Path

import pytest

from recall.config import Settings
from recall.memory.scope import TenantScope


def test_defaults_when_nothing_is_set() -> None:
    settings = Settings.from_env({})

    assert settings.sources == ("mic", "system")
    assert settings.ws_port == 8765
    assert settings.hf_token is None
    assert settings.scope is None


def test_values_are_read_from_the_environment() -> None:
    settings = Settings.from_env(
        {
            "RECALL_SOURCES": "mic",
            "RECALL_WS_PORT": "9000",
            "RECALL_WHISPER_MODEL": "tiny",
            "RECALL_MODEL_DIR": "/models",
            "HF_TOKEN": "secret",
        }
    )

    assert settings == Settings(("mic",), 9000, "tiny", Path("/models"), "secret")


@pytest.mark.parametrize(
    "env",
    [
        {"RECALL_SOURCES": "mic,speakers"},
        {"RECALL_SOURCES": ""},
        {"RECALL_WS_PORT": "abc"},
        {"RECALL_WS_PORT": "70000"},
        {"RECALL_TENANT_ID": "acme"},
        {"RECALL_PROJECT_ID": "website"},
        {"RECALL_TENANT_ID": "a/b", "RECALL_PROJECT_ID": "website"},
    ],
)
def test_invalid_values_are_rejected_naming_the_variable(env: dict[str, str]) -> None:
    with pytest.raises(ValueError, match=next(iter(env))):
        Settings.from_env(env)


def test_tenant_and_project_together_enable_memory() -> None:
    settings = Settings.from_env(
        {
            "RECALL_TENANT_ID": "acme",
            "RECALL_PROJECT_ID": "website",
            "RECALL_MEMORY_DIR": "/data/memory",
        }
    )

    assert settings.scope == TenantScope("acme", "website")
    assert settings.memory_dir == Path("/data/memory")


def test_privacy_settings() -> None:
    defaults = Settings.from_env({})
    assert defaults.redact is True and defaults.retention_days is None
    configured = Settings.from_env({"RECALL_REDACT": "off", "RECALL_RETENTION_DAYS": "90"})
    assert configured.redact is False and configured.retention_days == 90
    for bad in ("0", "-5", "ninety"):
        with pytest.raises(ValueError, match="RECALL_RETENTION_DAYS"):
            Settings.from_env({"RECALL_RETENTION_DAYS": bad})


def test_meeting_lifecycle_settings() -> None:
    settings = Settings.from_env(
        {
            "RECALL_AUTO_PROPOSE": "calendar, jira:WEB ,github:acme/web",
            "RECALL_IDLE_END_MINUTES": "5",
            "RECALL_EXIT_WHEN_IDLE": "1",
            "RECALL_RECORD_AUDIO": "on",
        }
    )
    assert settings.auto_propose == ("calendar", "jira:WEB", "github:acme/web")
    assert settings.idle_end_minutes == 5
    assert settings.exit_when_idle and settings.record_audio and not settings.llm_fact_check
    with pytest.raises(ValueError, match="RECALL_AUTO_PROPOSE"):
        Settings.from_env({"RECALL_AUTO_PROPOSE": "e-mail"})
    with pytest.raises(ValueError, match="RECALL_IDLE_END_MINUTES"):
        Settings.from_env({"RECALL_IDLE_END_MINUTES": "0"})


def test_code_dirs_must_be_folders(tmp_path) -> None:
    settings = Settings.from_env({"RECALL_CODE_DIRS": f"{tmp_path}, "})
    assert settings.code_dirs == (tmp_path,)
    with pytest.raises(ValueError, match="RECALL_CODE_DIRS"):
        Settings.from_env({"RECALL_CODE_DIRS": str(tmp_path / "missing")})


def test_risk_tracking_is_on_and_workload_check_off_by_default() -> None:
    settings = Settings.from_env({})
    assert settings.risk_tracking and not settings.workload_check
    assert not Settings.from_env({"RECALL_RISK_TRACKING": "0"}).risk_tracking


def test_meeting_languages_are_read_and_checked() -> None:
    assert Settings.from_env({"RECALL_MEETING_LANGUAGES": "en, TR,sq"}).meeting_languages == ("en", "tr", "sq")
    assert Settings.from_env({}).meeting_languages == ()
    with pytest.raises(ValueError, match="language code"):
        Settings.from_env({"RECALL_MEETING_LANGUAGES": "english"})
