# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Diagnostics: useful for a bug report, and never carrying secrets or personal data."""

import logging
from pathlib import Path

from continuum.diagnostics import log_to_file, report


def test_the_report_names_settings_but_never_secret_values(tmp_path: Path) -> None:
    log = tmp_path / "engine.log"
    log.write_text(
        "2026-10-16 INFO Loading Whisper model 'base'\n"
        "2026-10-16 WARNING GitHub refused token ghp-supersecret123 for ana@acme.com\n"
        "2026-10-16 INFO Call Ana on +90 532 123 45 67\n"
    )
    env = {
        "CONTINUUM_WHISPER_MODEL": "base",
        "CONTINUUM_LANGUAGE": "tr",
        "GITHUB_TOKEN": "ghp-supersecret123",
        "CONTINUUM_LLM_API_KEY": "gsk-abc123",
        "HOME": "/Users/ana",
        "CONTINUUM_TENANT_ID": "acme",
        "CONTINUUM_PROJECT_ID": "web",
    }
    text = report(env, log)

    assert "`CONTINUUM_WHISPER_MODEL` = `base`" in text and "`GITHUB_TOKEN` is set" in text
    assert "`CONTINUUM_LLM_API_KEY` is set" in text and "gsk-abc123" not in text
    assert "ghp-supersecret123" not in text and "[secret]" in text
    assert "ana@acme.com" not in text and "532 123" not in text
    assert "HOME" not in text  # unrelated environment variables are left out
    assert "Loading Whisper model 'base'" in text
    assert "## Configuration problems\n\n- none" in text


def test_the_log_is_kept_in_a_private_file(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "engine.log"
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        log_to_file(path)
        logging.getLogger("continuum.test").warning("engine started")
        for handler in root.handlers:
            handler.flush()
        assert "engine started" in path.read_text()
    finally:
        for handler in root.handlers[len(before):]:
            root.removeHandler(handler)
            handler.close()
