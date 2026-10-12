# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Runs an action once a human has approved it.

This module is deliberately not reachable from the MCP server: the model can
propose actions, but only code invoked by a person (the review command or the
desktop app) calls :func:`approve`.
"""

import logging

import httpx

from continuum.actions import github
from continuum.actions.settings import ActionSettings
from continuum.actions.store import Action, ActionStore

logger = logging.getLogger(__name__)


def approve(
    store: ActionStore, action_id: str, settings: ActionSettings, client: httpx.Client
) -> Action:
    """Execute a pending action exactly once and record the outcome.

    The action is claimed first, so a second approval of the same id fails
    instead of repeating the side effect. The stored content is re-validated
    and the repository allowlist re-checked at execution time, in case either
    changed since the proposal. Any failure is recorded on the action
    (status ``failed``) rather than raised.

    Raises:
        KeyError: if no action has this id.
        RuntimeError: if the action is not pending (already decided).
        ValueError: if the stored action was altered after it was proposed.
    """
    action = store.claim(action_id)
    try:
        if action.kind != github.KIND:
            raise ValueError(f"unknown action kind {action.kind!r}")
        issue = github.GitHubIssue.from_payload(action.payload)
        github.require_allowed_repo(issue, settings.github_repos)
        if not settings.github_token:
            raise RuntimeError("GITHUB_TOKEN is not set, so the issue cannot be created")
        url = github.create_issue(issue, settings.github_token, client)
    except Exception as error:
        logger.exception("Approved action %s failed", action_id)
        return store.finish(action_id, succeeded=False, result=str(error))
    return store.finish(action_id, succeeded=True, result=url)
