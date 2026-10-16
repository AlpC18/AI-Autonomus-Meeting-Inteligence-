# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Validated proposals: the one place that decides what may be queued.

The MCP tools and the meeting summarizer both queue actions through these
functions, so every proposal passes the same content checks and the same
permission check (allowlist or configured connector). Queuing never sends
anything; a person approves each action later.
"""

from collections.abc import Sequence
from typing import Any

from continuum.actions import calendar, github, jira, slack
from continuum.actions.settings import ActionSettings
from continuum.actions.store import Action, ActionStore

Proposal = tuple[str, dict[str, Any]]
"""An action kind and its validated payload, ready for :func:`queue`."""


def github_issue(
    settings: ActionSettings, repo: str, title: str, body: str = "", labels: Sequence[str] = ()
) -> Proposal:
    """Validate a GitHub issue for an allowed repository.

    Raises:
        ValueError: if a field is invalid.
        PermissionError: if the repository is not allowed.
    """
    issue = github.GitHubIssue(repo, title, body, tuple(labels))
    github.require_allowed_repo(issue, settings.github_repos)
    return github.KIND, issue.to_payload()


def jira_issue(
    settings: ActionSettings, project: str, summary: str, body: str = "", labels: Sequence[str] = ()
) -> Proposal:
    """Validate a Jira Task for an allowed project on the configured site.

    Raises:
        ValueError: if a field is invalid.
        PermissionError: if Jira is not configured or the project is not allowed.
    """
    jira.require_access(settings.jira)
    issue = jira.JiraIssue(project, summary, body, tuple(labels))
    jira.require_allowed_project(issue, settings.jira_projects)
    return jira.KIND, issue.to_payload()


def slack_message(settings: ActionSettings, text: str) -> Proposal:
    """Validate a message for the configured Slack channel.

    Raises:
        ValueError: if the text is empty or too long.
        PermissionError: if Slack is not configured.
    """
    slack.require_webhook(settings.slack_webhook_url)
    return slack.KIND, slack.SlackMessage(text).to_payload()


def calendar_deadline(
    settings: ActionSettings, title: str, due: str, description: str = ""
) -> Proposal:
    """Validate an all-day deadline for the configured Google Calendar.

    Raises:
        ValueError: if a field is invalid.
        PermissionError: if Google Calendar is not configured.
    """
    calendar.require_access(settings.google)
    return calendar.KIND, calendar.CalendarDeadline(title, due, description).to_payload()


def queue(store: ActionStore, proposal: Proposal) -> Action:
    """Queue a validated proposal for human approval.

    Raises:
        RuntimeError: if too many actions are already waiting.
    """
    kind, payload = proposal
    return store.propose(kind, payload)
