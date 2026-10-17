# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Connection test: each configured service is tried once and reported without its token."""

import httpx

from recall.connections import Result, check

PAGE = "0123456789abcdef0123456789abcdef"
ENV = {
    "RECALL_LLM_PROVIDER": "groq",
    "GROQ_API_KEY": "gsk-secret",
    "GITHUB_TOKEN": "ghp-secret",
    "RECALL_GITHUB_REPOS": "acme/web,acme/private",
    "GITLAB_TOKEN": "glpat-secret",
    "RECALL_JIRA_SITE": "https://acme.atlassian.net",
    "JIRA_EMAIL": "me@acme.com",
    "JIRA_API_TOKEN": "jira-secret",
    "RECALL_JIRA_PROJECTS": "WEB",
    "NOTION_TOKEN": "ntn-secret",
    "RECALL_NOTION_PAGE_ID": PAGE,
    "GOOGLE_CLIENT_ID": "id",
    "GOOGLE_CLIENT_SECRET": "google-secret",
    "GOOGLE_REFRESH_TOKEN": "refresh-secret",
    "HF_TOKEN": "hf-secret",
    "RECALL_SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T/B/x",
}

REPLIES = {
    "https://api.github.com/user": (200, {"login": "ana"}),
    "https://api.github.com/repos/acme/web": (200, {}),
    "https://api.github.com/repos/acme/private": (404, {"message": "Not Found"}),
    "https://gitlab.com/api/v4/user": (200, {"username": "ana.s"}),
    "https://acme.atlassian.net/rest/api/3/myself": (200, {"displayName": "Ana Silva"}),
    "https://acme.atlassian.net/rest/api/3/project/WEB": (200, {}),
    f"https://api.notion.com/v1/pages/{PAGE}": (404, {"message": "Could not find page"}),
    "https://oauth2.googleapis.com/token": (200, {"access_token": "t"}),
    "https://huggingface.co/api/whoami-v2": (401, {"error": "Invalid credentials"}),
}


class Answers:
    def complete(self, system: str, user: str) -> str:
        return "OK"


def handler(request: httpx.Request) -> httpx.Response:
    status, body = REPLIES[str(request.url)]
    return httpx.Response(status, json=body)


def test_every_configured_service_is_checked_and_reported() -> None:
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        results = check(ENV, client, lambda settings: Answers())

    by_service = {result.service: result for result in results}
    assert [result.service for result in results] == [
        "AI provider (groq)", "GitHub", "GitLab", "Jira", "Notion", "Google", "Hugging Face", "Slack",
    ]
    assert by_service["AI provider (groq)"].ok is True
    assert by_service["GitHub"] == Result(
        "GitHub", False, "signed in as ana, but cannot see acme/private (HTTP 404: Not Found)"
    )
    assert by_service["GitLab"] == Result("GitLab", True, "signed in as ana.s")
    assert by_service["Jira"] == Result("Jira", True, "signed in as Ana Silva")
    assert by_service["Notion"].ok is False and "share it with the integration" in by_service["Notion"].detail
    assert by_service["Google"].ok is True
    assert by_service["Hugging Face"] == Result("Hugging Face", False, "HTTP 401: Invalid credentials")
    assert by_service["Slack"].ok is None
    assert not any("secret" in result.detail for result in results)


def test_unreachable_services_and_ai_refusals_are_failures() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network")

    class Refuses:
        def complete(self, system: str, user: str) -> str:
            raise RuntimeError("groq refused the request (HTTP 401): invalid key")

    env = {key: ENV[key] for key in ("RECALL_LLM_PROVIDER", "GROQ_API_KEY", "GITHUB_TOKEN")}
    with httpx.Client(transport=httpx.MockTransport(down)) as client:
        results = check(env, client, lambda settings: Refuses())

    assert results == [
        Result("AI provider (groq)", False, "groq refused the request (HTTP 401): invalid key"),
        Result("GitHub", False, "could not be reached (ConnectError)"),
    ]


def test_nothing_configured_means_nothing_to_check() -> None:
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert check({}, client) == []
