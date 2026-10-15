# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Runs an action once a human has approved it.

This module is deliberately not reachable from the MCP server: the model can
propose actions, but only code invoked by a person (the review command or the
desktop app) calls :func:`approve`.
"""

import logging

import httpx

from continuum.actions import calendar, github, gmail, jira, slack
from continuum.actions.settings import ActionSettings
from continuum.actions.store import Action, ActionStore

logger = logging.getLogger(__name__)


def approve(
    store: ActionStore, action_id: str, settings: ActionSettings, client: httpx.Client
) -> Action:
    """Execute a pending action exactly once and record the outcome.

    The action is claimed first, so a second approval of the same id fails
    instead of repeating the side effect. The stored content is re-validated
    and the connector's permission (repository or project allowlist,
    configured webhook or calendar) re-checked at execution time, in case either changed since
    the proposal. Any failure is recorded on the action
    (status ``failed``) rather than raised.

    Raises:
        KeyError: if no action has this id.
        RuntimeError: if the action is not pending (already decided).
        ValueError: if the stored action was altered after it was proposed.
    """
    action = store.claim(action_id)
    try:
        result = _execute(action, settings, client)
    except Exception as error:  # noqa: BLE001 - every failure is recorded on the action
        logger.error("Approved action %s failed: %s", action_id, error)
        return store.finish(action_id, succeeded=False, result=str(error))
    return store.finish(action_id, succeeded=True, result=result)


def _execute(action: Action, settings: ActionSettings, client: httpx.Client) -> str:
    """Run one claimed action and return what to record as its result."""
    if action.kind == github.KIND:
        issue = github.GitHubIssue.from_payload(action.payload)
        github.require_allowed_repo(issue, settings.github_repos)
        if not settings.github_token:
            raise RuntimeError("GITHUB_TOKEN is not set, so the issue cannot be created")
        return github.create_issue(issue, settings.github_token, client)
    if action.kind == slack.KIND:
        message = slack.SlackMessage.from_payload(action.payload)
        return slack.send_message(message, slack.require_webhook(settings.slack_webhook_url), client)
    if action.kind == calendar.KIND:
        deadline = calendar.CalendarDeadline.from_payload(action.payload)
        access = calendar.require_access(settings.google)
        return calendar.create_deadline(deadline, access, settings.google_calendar_id, client)
    if action.kind == jira.KIND:
        jira_issue = jira.JiraIssue.from_payload(action.payload)
        jira.require_allowed_project(jira_issue, settings.jira_projects)
        return jira.create_issue(jira_issue, jira.require_access(settings.jira), client)
    if action.kind == gmail.KIND:
        recap = gmail.EmailRecap.from_payload(action.payload)
        return gmail.send(recap, calendar.require_access(settings.google), client)
    raise ValueError(f"unknown action kind {action.kind!r}")
