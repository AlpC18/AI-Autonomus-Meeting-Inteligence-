# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""GitLab: approved issues are created as proposed, and promised dates are checked against open issues."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

from recall.actions import gitlab
from recall.actions.approval import approve
from recall.actions.gitlab import GitLabAccess, GitLabIssue
from recall.actions.server import mcp
from recall.actions.settings import ActionSettings
from recall.actions.store import ActionStore
from recall.context.risk import Workload
from recall.context.workload import GitLabWorkload
from recall.summarize_cli import build_proposals
from recall.summary import ActionItem, MeetingSummary

PROJECT = "acme/platform/web"
ACCESS = GitLabAccess("https://gitlab.example.com", "glpat-secret")
ISSUE = GitLabIssue(PROJECT, "Refactor payment API", "From the 14 Aug meeting.", ("meeting", "backend"))


def settings(tmp_path: Path, projects: tuple[str, ...] = (PROJECT,)) -> ActionSettings:
    return ActionSettings(tmp_path / "actions.db", gitlab=ACCESS, gitlab_projects=frozenset(projects))


def test_approval_creates_the_exact_issue_that_was_proposed(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"web_url": "https://gitlab.example.com/acme/platform/web/-/issues/3"})

    store = ActionStore(tmp_path / "actions.db")
    action = store.propose(gitlab.KIND, ISSUE.to_payload())
    done = approve(store, action.id, settings(tmp_path), httpx.Client(transport=httpx.MockTransport(handler)))

    assert done.status == "done"
    assert done.result.endswith("/-/issues/3")
    (request,) = seen
    assert str(request.url) == "https://gitlab.example.com/api/v4/projects/acme%2Fplatform%2Fweb/issues"
    assert request.headers["PRIVATE-TOKEN"] == "glpat-secret"
    assert json.loads(request.content) == {
        "title": "Refactor payment API",
        "description": "From the 14 Aug meeting.",
        "labels": "meeting,backend",
    }


def test_refusals_are_recorded_without_the_token(tmp_path: Path) -> None:
    store = ActionStore(tmp_path / "actions.db")
    action = store.propose(gitlab.KIND, ISSUE.to_payload())
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401, json={"message": "401 Unauthorized"})))

    done = approve(store, action.id, settings(tmp_path), client)

    assert done.status == "failed"
    assert "401" in done.result and "glpat-secret" not in done.result


def test_a_project_removed_from_the_allowlist_blocks_execution(tmp_path: Path) -> None:
    store = ActionStore(tmp_path / "actions.db")
    action = store.propose(gitlab.KIND, ISSUE.to_payload())
    client = httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("GitLab was called")))

    done = approve(store, action.id, settings(tmp_path, ()), client)

    assert done.status == "failed" and "not allowed" in done.result


@pytest.mark.parametrize(
    "kwargs",
    [
        {"project": "no-group", "title": "x"},
        {"project": "../etc/passwd", "title": "x"},
        {"project": PROJECT, "title": " "},
        {"project": PROJECT, "title": "x", "labels": ("a,b",)},
    ],
)
def test_malformed_issues_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        GitLabIssue(**kwargs)


@pytest.mark.parametrize("url", ["http://gitlab.com", "gitlab.com", "https://gitlab.com/?x=1"])
def test_only_https_instances_are_accepted(url: str) -> None:
    with pytest.raises(ValueError):
        GitLabAccess(url, "token")


def test_settings_default_to_gitlab_com() -> None:
    read = ActionSettings.from_env({"GITLAB_TOKEN": "t", "RECALL_GITLAB_PROJECTS": "a/b, c/d/e"})
    assert read.gitlab is not None and read.gitlab.url == "https://gitlab.com"
    assert read.gitlab_projects == {"a/b", "c/d/e"}
    assert ActionSettings.from_env({}).gitlab is None


async def test_mcp_tool_proposes_without_contacting_gitlab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECALL_ACTIONS_DB", str(tmp_path / "actions.db"))
    monkeypatch.setenv("RECALL_GITLAB_PROJECTS", PROJECT)
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-secret")

    async with Client(mcp) as client:
        result = await client.call_tool("recall_propose_gitlab_issue", {"project": PROJECT, "title": "Refactor"})

    assert result.data["status"] == "pending"
    (stored,) = ActionStore(tmp_path / "actions.db").pending()
    assert stored.kind == gitlab.KIND and stored.payload["project"] == PROJECT


def test_summary_action_items_become_gitlab_proposals(tmp_path: Path) -> None:
    summary = MeetingSummary("Planning.", (), (ActionItem("Ship the API", "Ana", "2026-10-20"),))
    built, errors = build_proposals(summary, [f"gitlab:{PROJECT}"], settings(tmp_path), "notes.md")
    assert errors == []
    assert [(kind, payload["title"]) for kind, payload in built] == [(gitlab.KIND, "Ship the API")]


def _gitlab(request: httpx.Request) -> httpx.Response:
    path = request.url.raw_path.decode().split("?")[0]
    if path == "/api/v4/user":
        return httpx.Response(200, json={"username": "me"})
    if path == "/api/v4/projects/acme%2Fweb/members/all":
        return httpx.Response(200, json=[{"username": "ana.s", "name": "Ana Silva"}, {"username": "bob", "name": "Bob"}])
    if path == "/api/v4/projects/acme%2Fweb/issues":
        assert request.url.params["state"] == "opened"
        return httpx.Response(
            200,
            json=[
                {"iid": 1, "due_date": "2026-10-15", "milestone": None},
                {"iid": 2, "due_date": None, "milestone": {"due_date": "2026-10-16"}},
                {"iid": 3, "due_date": None, "milestone": None},
            ],
        )
    return httpx.Response(404)


def test_gitlab_workload_counts_open_issues_and_due_dates() -> None:
    workload = GitLabWorkload(
        GitLabAccess("https://gitlab.com", "t"), ("acme/web",), httpx.Client(transport=httpx.MockTransport(_gitlab))
    )
    expected = Workload(open=3, due_by=2, source="GitLab")
    assert workload("me", date(2026, 10, 16)) == expected
    assert workload("Ana Silva", date(2026, 10, 16)) == expected
    assert workload("Nobody", date(2026, 10, 16)) is None
