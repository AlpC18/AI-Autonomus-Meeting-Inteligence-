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

from continuum.actions import calendar, github, slack
from continuum.actions.approval import approve
from continuum.actions.calendar import CalendarDeadline, GoogleAccess
from continuum.actions.github import GitHubIssue
from continuum.actions.server import mcp
from continuum.actions.settings import ActionSettings
from continuum.actions.slack import SlackMessage
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
        "continuum_propose_jira_issue",
        "continuum_propose_slack_message",
        "continuum_propose_calendar_deadline",
        "continuum_list_pending_actions",
        "continuum_search_meetings",
    }


WEBHOOK = "https://hooks.slack.com/services/T000/B000/secret-path"
GOOGLE = GoogleAccess("client-id", "client-secret", "refresh-token")
DEADLINE = CalendarDeadline("Send Q4 report", "2026-11-30", "Agreed in the budget meeting.")


class FakeService:
    """Answers every request with the next prepared response and records them."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.requests: list[httpx.Request] = []
        self._responses = iter(responses)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def connected(tmp_path: Path) -> ActionSettings:
    return ActionSettings(tmp_path / "actions.db", slack_webhook_url=WEBHOOK, google=GOOGLE)


def test_approved_slack_message_goes_to_the_configured_webhook_only(
    store: ActionStore, tmp_path: Path
) -> None:
    fake = FakeService(httpx.Response(200, text="ok"))
    action = store.propose(slack.KIND, SlackMessage("Budget approved: $35,000").to_payload())
    assert fake.requests == []

    done = approve(store, action.id, connected(tmp_path), fake.client())

    assert (done.status, done.result) == ("done", "Posted to Slack")
    (request,) = fake.requests
    assert str(request.url) == WEBHOOK
    assert json.loads(request.content) == {"text": "Budget approved: $35,000"}


def test_slack_failures_never_record_the_webhook_url(store: ActionStore, tmp_path: Path) -> None:
    for response in (
        httpx.Response(404, text="no_service"),
        httpx.ConnectError(f"cannot connect to {WEBHOOK}"),
    ):
        action = store.propose(slack.KIND, SlackMessage("hello").to_payload())

        done = approve(store, action.id, connected(tmp_path), FakeService(response).client())

        assert done.status == "failed"
        assert "secret-path" not in (done.result or "")


@pytest.mark.parametrize("webhook", [None, "https://evil.example/hooks.slack.com/x"])
def test_slack_message_is_not_sent_without_a_slack_webhook(
    store: ActionStore, tmp_path: Path, webhook: str | None
) -> None:
    fake = FakeService()
    action = store.propose(slack.KIND, SlackMessage("hello").to_payload())
    unconfigured = ActionSettings(tmp_path / "actions.db", slack_webhook_url=webhook)

    done = approve(store, action.id, unconfigured, fake.client())

    assert done.status == "failed"
    assert fake.requests == []


def test_approved_deadline_becomes_an_all_day_event(store: ActionStore, tmp_path: Path) -> None:
    fake = FakeService(
        httpx.Response(200, json={"access_token": "short-lived"}),
        httpx.Response(200, json={"htmlLink": "https://calendar.google.com/event?eid=1"}),
    )
    action = store.propose(calendar.KIND, DEADLINE.to_payload())

    done = approve(store, action.id, connected(tmp_path), fake.client())

    assert (done.status, done.result) == ("done", "https://calendar.google.com/event?eid=1")
    token_request, event_request = fake.requests
    assert token_request.url.host == "oauth2.googleapis.com"
    assert str(event_request.url).endswith("/calendars/primary/events")
    assert event_request.headers["Authorization"] == "Bearer short-lived"
    assert json.loads(event_request.content) == {
        "summary": "Send Q4 report",
        "description": "Agreed in the budget meeting.",
        "start": {"date": "2026-11-30"},
        "end": {"date": "2026-12-01"},
    }


def test_rejected_google_credentials_are_recorded_without_secrets(
    store: ActionStore, tmp_path: Path
) -> None:
    fake = FakeService(
        httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token revoked"})
    )
    action = store.propose(calendar.KIND, DEADLINE.to_payload())

    done = approve(store, action.id, connected(tmp_path), fake.client())

    assert done.status == "failed"
    assert "Token revoked" in (done.result or "")
    assert "client-secret" not in (done.result or "") and "refresh-token" not in (done.result or "")
    assert len(fake.requests) == 1


def test_deadline_is_not_created_when_google_is_not_configured(
    store: ActionStore, tmp_path: Path
) -> None:
    fake = FakeService()
    action = store.propose(calendar.KIND, DEADLINE.to_payload())

    done = approve(store, action.id, ActionSettings(tmp_path / "actions.db"), fake.client())

    assert done.status == "failed"
    assert fake.requests == []


@pytest.mark.parametrize(
    "build",
    [
        lambda: SlackMessage("  "),
        lambda: SlackMessage("x" * 3001),
        lambda: CalendarDeadline("", "2026-11-30"),
        lambda: CalendarDeadline("Report", "30/11/2026"),
        lambda: CalendarDeadline("Report", "2026-11-31"),
        lambda: CalendarDeadline("Report", "20261130"),
        lambda: CalendarDeadline.from_payload({"title": "Report"}),
        lambda: SlackMessage.from_payload({}),
    ],
)
def test_malformed_messages_and_deadlines_are_rejected(build) -> None:
    with pytest.raises(ValueError):
        build()


def test_settings_need_all_three_google_values() -> None:
    partial = {"GOOGLE_CLIENT_ID": "a", "GOOGLE_CLIENT_SECRET": "b"}

    assert ActionSettings.from_env(partial).google is None
    assert ActionSettings.from_env({**partial, "GOOGLE_REFRESH_TOKEN": "c"}).google == GoogleAccess(
        "a", "b", "c"
    )


async def test_tools_refuse_proposals_for_unconfigured_connectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTINUUM_ACTIONS_DB", str(tmp_path / "actions.db"))
    for name in ("CONTINUUM_SLACK_WEBHOOK_URL", "GOOGLE_CLIENT_ID"):
        monkeypatch.delenv(name, raising=False)

    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="Slack is not configured"):
            await client.call_tool("continuum_propose_slack_message", {"text": "hi"})
        with pytest.raises(ToolError, match="Google Calendar is not configured"):
            await client.call_tool(
                "continuum_propose_calendar_deadline", {"title": "Report", "due": "2026-11-30"}
            )
        assert await client.call_tool("continuum_list_pending_actions", {}) is not None

    assert ActionStore(tmp_path / "actions.db").pending() == []


async def test_tools_queue_slack_and_calendar_proposals_without_sending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTINUUM_ACTIONS_DB", str(tmp_path / "actions.db"))
    monkeypatch.setenv("CONTINUUM_SLACK_WEBHOOK_URL", WEBHOOK)
    for name, value in zip(
        ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"), "abc", strict=True
    ):
        monkeypatch.setenv(name, value)

    async with Client(mcp) as client:
        await client.call_tool("continuum_propose_slack_message", {"text": "Budget approved"})
        await client.call_tool(
            "continuum_propose_calendar_deadline", {"title": "Report", "due": "2026-11-30"}
        )

    pending = ActionStore(tmp_path / "actions.db").pending()
    assert [(action.kind, action.status) for action in pending] == [
        (slack.KIND, "pending"),
        (calendar.KIND, "pending"),
    ]


async def test_meeting_search_tool_explains_when_memory_is_not_set_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CONTINUUM_TENANT_ID", raising=False)
    monkeypatch.delenv("CONTINUUM_PROJECT_ID", raising=False)

    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="CONTINUUM_TENANT_ID"):
            await client.call_tool("continuum_search_meetings", {"query": "budget"})

        monkeypatch.setenv("CONTINUUM_TENANT_ID", "acme")
        monkeypatch.setenv("CONTINUUM_PROJECT_ID", "website")
        monkeypatch.setenv("CONTINUUM_MEMORY_DIR", str(tmp_path / "nothing-here"))
        with pytest.raises(ToolError, match="No memory has been stored"):
            await client.call_tool("continuum_search_meetings", {"query": "budget"})
        with pytest.raises(ToolError):
            await client.call_tool("continuum_search_meetings", {"query": "budget", "limit": 500})
