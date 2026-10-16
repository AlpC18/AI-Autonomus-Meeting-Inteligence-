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
