# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Settings parsing: defaults, overrides, and rejection of bad values."""

from pathlib import Path

import pytest

from continuum.config import Settings
from continuum.memory.scope import TenantScope


def test_defaults_when_nothing_is_set() -> None:
    settings = Settings.from_env({})

    assert settings.sources == ("mic", "system")
    assert settings.ws_port == 8765
    assert settings.hf_token is None
    assert settings.scope is None


def test_values_are_read_from_the_environment() -> None:
    settings = Settings.from_env(
        {
            "CONTINUUM_SOURCES": "mic",
            "CONTINUUM_WS_PORT": "9000",
            "CONTINUUM_WHISPER_MODEL": "tiny",
            "CONTINUUM_MODEL_DIR": "/models",
            "HF_TOKEN": "secret",
        }
    )

    assert settings == Settings(("mic",), 9000, "tiny", Path("/models"), "secret")


@pytest.mark.parametrize(
    "env",
    [
        {"CONTINUUM_SOURCES": "mic,speakers"},
        {"CONTINUUM_SOURCES": ""},
        {"CONTINUUM_WS_PORT": "abc"},
        {"CONTINUUM_WS_PORT": "70000"},
        {"CONTINUUM_TENANT_ID": "acme"},
        {"CONTINUUM_PROJECT_ID": "website"},
        {"CONTINUUM_TENANT_ID": "a/b", "CONTINUUM_PROJECT_ID": "website"},
    ],
)
def test_invalid_values_are_rejected_naming_the_variable(env: dict[str, str]) -> None:
    with pytest.raises(ValueError, match=next(iter(env))):
        Settings.from_env(env)


def test_tenant_and_project_together_enable_memory() -> None:
    settings = Settings.from_env(
        {
            "CONTINUUM_TENANT_ID": "acme",
            "CONTINUUM_PROJECT_ID": "website",
            "CONTINUUM_MEMORY_DIR": "/data/memory",
        }
    )

    assert settings.scope == TenantScope("acme", "website")
    assert settings.memory_dir == Path("/data/memory")


def test_privacy_settings() -> None:
    defaults = Settings.from_env({})
    assert defaults.redact is True and defaults.retention_days is None
    configured = Settings.from_env({"CONTINUUM_REDACT": "off", "CONTINUUM_RETENTION_DAYS": "90"})
    assert configured.redact is False and configured.retention_days == 90
    for bad in ("0", "-5", "ninety"):
        with pytest.raises(ValueError, match="CONTINUUM_RETENTION_DAYS"):
            Settings.from_env({"CONTINUUM_RETENTION_DAYS": bad})


def test_meeting_lifecycle_settings() -> None:
    settings = Settings.from_env(
        {
            "CONTINUUM_AUTO_PROPOSE": "calendar, jira:WEB ,github:acme/web",
            "CONTINUUM_IDLE_END_MINUTES": "5",
            "CONTINUUM_EXIT_WHEN_IDLE": "1",
            "CONTINUUM_RECORD_AUDIO": "on",
        }
    )
    assert settings.auto_propose == ("calendar", "jira:WEB", "github:acme/web")
    assert settings.idle_end_minutes == 5
    assert settings.exit_when_idle and settings.record_audio and not settings.llm_fact_check
    with pytest.raises(ValueError, match="CONTINUUM_AUTO_PROPOSE"):
        Settings.from_env({"CONTINUUM_AUTO_PROPOSE": "email"})
    with pytest.raises(ValueError, match="CONTINUUM_IDLE_END_MINUTES"):
        Settings.from_env({"CONTINUUM_IDLE_END_MINUTES": "0"})
