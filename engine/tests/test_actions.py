# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Actions: the model can only propose; one approval runs an action exactly once."""

import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from continuum.actions import github
from continuum.actions.approval import approve
from continuum.actions.github import GitHubIssue
from continuum.actions.server import mcp
from continuum.actions.settings import ActionSettings
from continuum.actions.store import MAX_PENDING, ActionStore

REPO = "acme/website"
ISSUE = GitHubIssue(REPO, "Refactor payment API", "From the 14 Aug meeting.", ("meeting",))


class FakeGitHub:
    """Stands in for api.github.com and records what it was asked to create."""

    def __init__(self, status: int = 201) -> None:
        self.requests: list[httpx.Request] = []
        self._status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._status != 201:
            return httpx.Response(self._status, json={"message": "Bad credentials"})
        return httpx.Response(201, json={"html_url": f"https://github.com/{REPO}/issues/7"})

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


@pytest.fixture
def store(tmp_path: Path) -> ActionStore:
    return ActionStore(tmp_path / "actions.db")


def settings(tmp_path: Path, repos: tuple[str, ...] = (REPO,)) -> ActionSettings:
    return ActionSettings(tmp_path / "actions.db", frozenset(repos), "token-123")


def test_proposing_sends_nothing_and_waits_for_review(store: ActionStore) -> None:
    action = store.propose(github.KIND, ISSUE.to_payload())

    assert action.status == "pending"
    assert [pending.id for pending in store.pending()] == [action.id]


def test_approval_creates_the_exact_issue_that_was_proposed(
    store: ActionStore, tmp_path: Path
) -> None:
    fake = FakeGitHub()
    action = store.propose(github.KIND, ISSUE.to_payload())

    done = approve(store, action.id, settings(tmp_path), fake.client())

    assert done.status == "done"
    assert done.result == f"https://github.com/{REPO}/issues/7"
    (request,) = fake.requests
    assert request.url == f"https://api.github.com/repos/{REPO}/issues"
    assert request.headers["Authorization"] == "Bearer token-123"
    assert json.loads(request.content) == {
        "title": "Refactor payment API",
        "body": "From the 14 Aug meeting.",
        "labels": ["meeting"],
    }
    assert store.pending() == []


def test_an_action_cannot_be_approved_twice(store: ActionStore, tmp_path: Path) -> None:
    fake = FakeGitHub()
    action = store.propose(github.KIND, ISSUE.to_payload())
    approve(store, action.id, settings(tmp_path), fake.client())

    with pytest.raises(RuntimeError, match="not pending"):
        approve(store, action.id, settings(tmp_path), fake.client())
    assert len(fake.requests) == 1


def test_a_rejected_action_can_never_run(store: ActionStore, tmp_path: Path) -> None:
    fake = FakeGitHub()
    action = store.propose(github.KIND, ISSUE.to_payload())
    store.reject(action.id)

    with pytest.raises(RuntimeError, match="rejected"):
        approve(store, action.id, settings(tmp_path), fake.client())
    assert fake.requests == []


def test_repo_removed_from_allowlist_blocks_execution(store: ActionStore, tmp_path: Path) -> None:
    fake = FakeGitHub()
    action = store.propose(github.KIND, ISSUE.to_payload())

    done = approve(store, action.id, settings(tmp_path, repos=()), fake.client())

    assert done.status == "failed"
    assert "not allowed" in (done.result or "")
    assert fake.requests == []


def test_github_refusal_is_recorded_without_leaking_the_token(
    store: ActionStore, tmp_path: Path
) -> None:
    action = store.propose(github.KIND, ISSUE.to_payload())

    done = approve(store, action.id, settings(tmp_path), FakeGitHub(status=401).client())

    assert done.status == "failed"
    assert "401" in (done.result or "") and "Bad credentials" in (done.result or "")
    assert "token-123" not in (done.result or "")


def test_content_altered_after_proposal_is_refused(store: ActionStore, tmp_path: Path) -> None:
    fake = FakeGitHub()
    action = store.propose(github.KIND, ISSUE.to_payload())
    tampered = json.dumps({**ISSUE.to_payload(), "repo": "evil/repo"}, sort_keys=True)
    with sqlite3.connect(tmp_path / "actions.db") as connection:
        connection.execute("UPDATE actions SET payload = ? WHERE id = ?", (tampered, action.id))

    with pytest.raises(ValueError, match="altered"):
        approve(store, action.id, settings(tmp_path), fake.client())
    assert fake.requests == []


def test_unknown_action_id_is_an_error(store: ActionStore, tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        approve(store, "missing", settings(tmp_path), FakeGitHub().client())


def test_pending_queue_is_capped(store: ActionStore) -> None:
    for _ in range(MAX_PENDING):
        store.propose(github.KIND, ISSUE.to_payload())

    with pytest.raises(RuntimeError, match="already waiting"):
        store.propose(github.KIND, ISSUE.to_payload())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"repo": "not a repo", "title": "x"},
        {"repo": "acme/website/../other", "title": "x"},
        {"repo": REPO, "title": "  "},
        {"repo": REPO, "title": "x" * 257},
        {"repo": REPO, "title": "x", "body": "y" * 10_001},
        {"repo": REPO, "title": "x", "labels": tuple(str(n) for n in range(11))},
    ],
)
def test_malformed_issues_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        GitHubIssue(**kwargs)


async def test_mcp_tool_proposes_without_contacting_github(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTINUUM_ACTIONS_DB", str(tmp_path / "actions.db"))
    monkeypatch.setenv("CONTINUUM_GITHUB_REPOS", REPO)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "continuum_propose_github_issue", {"repo": REPO, "title": "Refactor payment API"}
        )
        pending = await client.call_tool("continuum_list_pending_actions")

    assert result.data["status"] == "pending"
    stored = ActionStore(tmp_path / "actions.db").pending()
    assert [action.id for action in stored] == [result.data["action_id"]]
    assert stored[0].payload["title"] == "Refactor payment API"
    assert len(pending.data) == 1


async def test_mcp_tool_refuses_a_repo_that_is_not_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTINUUM_ACTIONS_DB", str(tmp_path / "actions.db"))
    monkeypatch.setenv("CONTINUUM_GITHUB_REPOS", REPO)

    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="not allowed"):
            await client.call_tool(
                "continuum_propose_github_issue", {"repo": "evil/repo", "title": "x"}
            )

    assert ActionStore(tmp_path / "actions.db").pending() == []


async def test_server_exposes_no_way_to_approve_or_execute() -> None:
    async with Client(mcp) as client:
        names = {tool.name for tool in await client.list_tools()}

    assert names == {
        "continuum_health",
        "continuum_propose_github_issue",
        "continuum_list_pending_actions",
    }
