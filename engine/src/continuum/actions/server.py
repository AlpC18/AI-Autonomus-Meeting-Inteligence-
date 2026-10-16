# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""FastMCP server for the Continuum action engine.

Registers the MCP tools an LLM can call. Tools here can only *propose*
actions on external systems. Nothing is sent anywhere until a person approves
the exact proposal through the review command or the desktop app; there is
deliberately no tool that approves or executes.
"""

import os
from importlib.metadata import version
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from continuum.actions import github
from continuum.actions.settings import ActionSettings
from continuum.actions.store import ActionStore

mcp = FastMCP("continuum_actions")
"""The server instance. Import this to register tools or to test in-memory."""


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, idempotentHint=True, openWorldHint=False
    )
)
def continuum_health() -> dict[str, str]:
    """Report whether the Continuum action server is running.

    Read-only and side-effect free: it contacts no external service. Use it to
    confirm the server is reachable before calling other tools.

    Returns:
        ``{"status": "ok", "version": "<installed engine version>"}``.
    """
    return {"status": "ok", "version": version("continuum")}


def _store() -> tuple[ActionStore, ActionSettings]:
    settings = ActionSettings.from_env(os.environ)
    return ActionStore(settings.database), settings


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
    )
)
def continuum_propose_github_issue(
    repo: Annotated[str, Field(description="Repository as 'owner/name', e.g. 'acme/website'")],
    title: Annotated[str, Field(description="Issue title, at most 256 characters")],
    body: Annotated[str, Field(description="Issue body in Markdown, at most 10000 characters")] = "",
    labels: Annotated[list[str] | None, Field(description="Up to 10 label names")] = None,
) -> dict[str, Any]:
    """Propose creating a GitHub issue. Does NOT create it.

    The proposal is queued for a human, who sees the exact repository, title,
    body and labels and decides. Only repositories the user allowed in
    CONTINUUM_GITHUB_REPOS are accepted. Tell the user the issue is waiting
    for their approval; do not claim it was created.

    Returns:
        ``{"action_id": ..., "status": "pending", "message": ...}``.
    """
    store, settings = _store()
    try:
        issue = github.GitHubIssue(repo, title, body, tuple(labels or ()))
        github.require_allowed_repo(issue, settings.github_repos)
        action = store.propose(github.KIND, issue.to_payload())
    except (ValueError, PermissionError, RuntimeError) as error:
        raise ToolError(str(error)) from error
    return {
        "action_id": action.id,
        "status": action.status,
        "message": "Queued for human approval. Nothing has been sent to GitHub yet.",
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False))
def continuum_list_pending_actions() -> list[dict[str, Any]]:
    """List proposed actions that are still waiting for the user's decision.

    Read-only. Use it to remind the user what awaits approval; decisions
    themselves can only be made by the user.
    """
    store, _settings = _store()
    return [
        {"action_id": action.id, "kind": action.kind, "payload": action.payload}
        for action in store.pending()
    ]


def main() -> None:
    """Run the server over stdio (the ``continuum-actions`` console script).

    Blocks until the client disconnects.
    """
    mcp.run()
