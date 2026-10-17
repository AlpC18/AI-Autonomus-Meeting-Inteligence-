# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Jira issues: proposed only into allowed projects, created once on approval."""

import base64
import json
from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from recall.actions import jira
from recall.actions.approval import approve
from recall.actions.jira import JiraAccess, JiraIssue
from recall.actions.server import mcp
from recall.actions.settings import ActionSettings
from recall.actions.store import ActionStore

SITE = "https://acme.atlassian.net"
ACCESS = JiraAccess(SITE, "pm@acme.test", "api-token-123")
ISSUE = JiraIssue("WEB", "Refactor payment API", "From the budget meeting.\n\nOwner: Ana", ("meeting",))


def recording(*responses: httpx.Response | Exception) -> tuple[list[httpx.Request], httpx.Client]:
    """A client whose transport answers with ``responses`` in order and records requests."""
    requests: list[httpx.Request] = []
    queue = iter(responses)

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        response = next(queue)
        if isinstance(response, Exception):
            raise response
        return response

    return requests, httpx.Client(transport=httpx.MockTransport(handle))


def settings(tmp_path: Path, projects: tuple[str, ...] = ("WEB",), access=ACCESS) -> ActionSettings:
    return ActionSettings(tmp_path / "actions.db", jira=access, jira_projects=frozenset(projects))


@pytest.fixture
def store(tmp_path: Path) -> ActionStore:
    return ActionStore(tmp_path / "actions.db")


def test_approved_issue_is_created_in_the_allowed_project(
    store: ActionStore, tmp_path: Path
) -> None:
    requests, client = recording(httpx.Response(201, json={"id": "10001", "key": "WEB-42"}))
    action = store.propose(jira.KIND, ISSUE.to_payload())
    assert requests == []

    done = approve(store, action.id, settings(tmp_path), client)

    assert (done.status, done.result) == ("done", f"{SITE}/browse/WEB-42")
    (request,) = requests
    assert str(request.url) == f"{SITE}/rest/api/3/issue"
    expected = base64.b64encode(b"pm@acme.test:api-token-123").decode()
    assert request.headers["Authorization"] == f"Basic {expected}"
    fields = json.loads(request.content)["fields"]
    assert fields["project"] == {"key": "WEB"}
    assert fields["summary"] == "Refactor payment API"
    assert fields["issuetype"] == {"name": "Task"}
    assert fields["labels"] == ["meeting"]
    paragraphs = [block["content"][0]["text"] for block in fields["description"]["content"]]
    assert paragraphs == ["From the budget meeting.", "Owner: Ana"]


def test_issue_without_body_sends_no_description(store: ActionStore, tmp_path: Path) -> None:
    requests, client = recording(httpx.Response(201, json={"key": "WEB-1"}))
    action = store.propose(jira.KIND, JiraIssue("WEB", "Title only").to_payload())

    approve(store, action.id, settings(tmp_path), client)

    assert "description" not in json.loads(requests[0].content)["fields"]


def test_project_removed_from_allowlist_blocks_execution(
    store: ActionStore, tmp_path: Path
) -> None:
    requests, client = recording()
    action = store.propose(jira.KIND, ISSUE.to_payload())

    done = approve(store, action.id, settings(tmp_path, projects=()), client)

    assert done.status == "failed"
    assert "not allowed" in (done.result or "")
    assert requests == []


def test_issue_is_not_created_without_jira_credentials(store: ActionStore, tmp_path: Path) -> None:
    requests, client = recording()
    action = store.propose(jira.KIND, ISSUE.to_payload())

    done = approve(store, action.id, settings(tmp_path, access=None), client)

    assert done.status == "failed"
    assert "Jira is not configured" in (done.result or "")
    assert requests == []


def test_jira_failures_never_record_the_token(store: ActionStore, tmp_path: Path) -> None:
    for response in (
        httpx.Response(401, json={"errorMessages": ["Client must be authenticated"]}),
        httpx.Response(400, json={"errors": {"labels": "bad label"}}),
        httpx.ConnectError("cannot connect with api-token-123"),
    ):
        _requests, client = recording(response)
        action = store.propose(jira.KIND, ISSUE.to_payload())

        done = approve(store, action.id, settings(tmp_path), client)

        assert done.status == "failed"
        assert "api-token-123" not in (done.result or "")


def test_jira_refusal_reports_jiras_own_message(store: ActionStore, tmp_path: Path) -> None:
    _requests, client = recording(
        httpx.Response(400, json={"errorMessages": [], "errors": {"labels": "bad label"}})
    )
    action = store.propose(jira.KIND, ISSUE.to_payload())

    done = approve(store, action.id, settings(tmp_path), client)

    assert "HTTP 400" in (done.result or "") and "bad label" in (done.result or "")


def test_access_has_no_repr_that_could_leak_the_token() -> None:
    assert "api-token-123" not in repr(ACCESS)
    assert "api-token-123" not in str(ACCESS)


@pytest.mark.parametrize(
    "build",
    [
        lambda: JiraIssue("web", "lower-case key"),
        lambda: JiraIssue("WEB-1", "not a key"),
        lambda: JiraIssue("WEB", "  "),
        lambda: JiraIssue("WEB", "x" * 256),
        lambda: JiraIssue("WEB", "ok", "x" * 10_001),
        lambda: JiraIssue("WEB", "ok", "", ("has space",)),
        lambda: JiraIssue("WEB", "ok", "", tuple(f"l{i}" for i in range(11))),
        lambda: JiraIssue.from_payload({"project": "WEB"}),
        lambda: JiraAccess("https://evil.example", "a@b.c", "t"),
        lambda: JiraAccess("http://acme.atlassian.net", "a@b.c", "t"),
        lambda: JiraAccess("https://acme.atlassian.net.evil.example", "a@b.c", "t"),
    ],
)
def test_malformed_issues_and_sites_are_rejected(build) -> None:
    with pytest.raises(ValueError):
        build()


def test_settings_need_site_email_and_token() -> None:
    partial = {"RECALL_JIRA_SITE": SITE + "/", "JIRA_EMAIL": "pm@acme.test"}

    assert ActionSettings.from_env(partial).jira is None
    configured = ActionSettings.from_env(
        {**partial, "JIRA_API_TOKEN": "t", "RECALL_JIRA_PROJECTS": "WEB, ops ,"}
    )
    assert configured.jira is not None and configured.jira.site == SITE
    assert configured.jira_projects == frozenset({"WEB", "OPS"})


async def test_tool_queues_allowed_issues_and_refuses_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RECALL_ACTIONS_DB", str(tmp_path / "actions.db"))
    monkeypatch.setenv("RECALL_JIRA_SITE", SITE)
    monkeypatch.setenv("JIRA_EMAIL", "pm@acme.test")
    monkeypatch.setenv("JIRA_API_TOKEN", "t")
    monkeypatch.setenv("RECALL_JIRA_PROJECTS", "WEB")

    async with Client(mcp) as client:
        await client.call_tool(
            "recall_propose_jira_issue", {"project": "WEB", "summary": "Refactor payment API"}
        )
        with pytest.raises(ToolError, match="not allowed"):
            await client.call_tool("recall_propose_jira_issue", {"project": "HR", "summary": "x"})
        monkeypatch.delenv("JIRA_API_TOKEN")
        with pytest.raises(ToolError, match="Jira is not configured"):
            await client.call_tool("recall_propose_jira_issue", {"project": "WEB", "summary": "x"})

    pending = ActionStore(tmp_path / "actions.db").pending()
    assert [(action.kind, action.payload["project"]) for action in pending] == [(jira.KIND, "WEB")]


async def test_tool_explains_a_misconfigured_site(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RECALL_ACTIONS_DB", str(tmp_path / "actions.db"))
    monkeypatch.setenv("RECALL_JIRA_SITE", "https://jira.evil.example")
    monkeypatch.setenv("JIRA_EMAIL", "pm@acme.test")
    monkeypatch.setenv("JIRA_API_TOKEN", "t")

    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="atlassian.net"):
            await client.call_tool("recall_propose_jira_issue", {"project": "WEB", "summary": "x"})
