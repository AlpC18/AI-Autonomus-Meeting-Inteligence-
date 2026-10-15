# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The settings screen's check reports every problem at once."""

from continuum.config_check import problems


def test_a_valid_configuration_has_no_problems(tmp_path) -> None:
    assert problems({"CONTINUUM_NOTES_DIR": str(tmp_path), "CONTINUUM_LLM_PROVIDER": "ollama"}) == []


def test_problems_from_every_area_are_reported_together() -> None:
    found = problems(
        {
            "CONTINUUM_TENANT_ID": "acme",  # project missing
            "CONTINUUM_JIRA_SITE": "https://jira.evil.example",
            "JIRA_EMAIL": "a@b.c",
            "JIRA_API_TOKEN": "t",
            "CONTINUUM_LLM_PROVIDER": "groq",  # key missing
        }
    )
    assert len(found) == 3
    assert any("CONTINUUM_PROJECT_ID" in problem for problem in found)
    assert any("atlassian.net" in problem for problem in found)
    assert any("GROQ_API_KEY" in problem for problem in found)
