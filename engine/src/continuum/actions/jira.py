# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The Jira issue action: validating a request and creating the issue on Jira Cloud."""

import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

import httpx

KIND = "jira_issue"
"""Action kind under which Jira issues are stored."""

ISSUE_TYPE = "Task"
"""Every proposal becomes a Task; the model cannot pick another issue type."""

_SITE = re.compile(r"https://[a-z0-9][a-z0-9-]{0,62}\.atlassian\.net")
_PROJECT = re.compile(r"[A-Z][A-Z0-9_]{1,9}")
_MAX_SUMMARY = 255
_MAX_BODY = 10_000
_MAX_LABELS = 10
_MAX_LABEL = 50


@dataclass(frozen=True, slots=True, repr=False)
class JiraAccess:
    """The user's Jira Cloud site and API token (with the account's email).

    Only ``https://<name>.atlassian.net`` sites are accepted, so the token is
    never sent anywhere else. Has no ``repr``, so the token cannot end up in
    a log line by accident.

    Raises:
        ValueError: on construction, if ``site`` is not an Atlassian Cloud site.
    """

    site: str
    email: str
    api_token: str

    def __post_init__(self) -> None:
        if not isinstance(self.site, str) or not _SITE.fullmatch(self.site):
            raise ValueError("Jira site must look like https://your-team.atlassian.net")


@dataclass(frozen=True, slots=True)
class JiraIssue:
    """A Jira issue someone wants to create in ``project`` (its key, e.g. ``WEB``).

    Raises:
        ValueError: on construction, describing the first invalid field.
    """

    project: str
    summary: str
    body: str = ""
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.project, str) or not _PROJECT.fullmatch(self.project):
            raise ValueError(f"project must be a Jira project key like 'WEB', got {self.project!r}")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("summary must not be empty")
        if len(self.summary) > _MAX_SUMMARY:
            raise ValueError(f"summary must be at most {_MAX_SUMMARY} characters")
        if not isinstance(self.body, str) or len(self.body) > _MAX_BODY:
            raise ValueError(f"body must be text of at most {_MAX_BODY} characters")
        if len(self.labels) > _MAX_LABELS:
            raise ValueError(f"at most {_MAX_LABELS} labels are allowed")
        for label in self.labels:
            if not isinstance(label, str) or not re.fullmatch(rf"\S{{1,{_MAX_LABEL}}}", label):
                raise ValueError(
                    f"each label must be 1-{_MAX_LABEL} characters without spaces, got {label!r}"
                )

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON-serialisable form stored with a pending action."""
        return {
            "project": self.project,
            "summary": self.summary,
            "body": self.body,
            "labels": list(self.labels),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "JiraIssue":
        """Rebuild (and re-validate) an issue from :meth:`to_payload` output.

        Raises:
            ValueError: if the payload is malformed or invalid.
        """
        try:
            return cls(
                project=payload["project"],
                summary=payload["summary"],
                body=payload.get("body", ""),
                labels=tuple(payload.get("labels", ())),
            )
        except (KeyError, TypeError) as error:
            raise ValueError(f"malformed Jira issue payload: {error}") from error


def require_access(access: JiraAccess | None) -> JiraAccess:
    """Return the configured Jira access, refusing when there is none.

    Raises:
        PermissionError: naming the variables that enable Jira.
    """
    if access is None:
        raise PermissionError(
            "Jira is not configured. Set CONTINUUM_JIRA_SITE, JIRA_EMAIL and "
            "JIRA_API_TOKEN to permit issues."
        )
    return access


def require_allowed_project(issue: JiraIssue, allowed_projects: Collection[str]) -> None:
    """Refuse an issue aimed at a project that was not explicitly allowed (deny by default).

    Raises:
        PermissionError: naming the project and how to allow it.
    """
    if issue.project not in allowed_projects:
        raise PermissionError(
            f"Jira project {issue.project!r} is not allowed. Add its key to "
            "CONTINUUM_JIRA_PROJECTS (comma-separated) to permit issues there."
        )


def _document(body: str) -> dict[str, Any]:
    """Body text as an Atlassian Document: one paragraph per blank-line-separated block."""
    blocks = [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": block}]}
            for block in blocks
        ],
    }


def _refusal(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    messages = [str(message) for message in data.get("errorMessages") or []]
    errors = data.get("errors") or {}
    if isinstance(errors, dict):
        messages += [f"{field}: {message}" for field, message in errors.items()]
    return "; ".join(messages)[:300]


def create_issue(issue: JiraIssue, access: JiraAccess, client: httpx.Client) -> str:
    """Create ``issue`` on Jira Cloud and return the new issue's browse URL.

    Changes an external system and cannot be undone from here; call it only
    after a human approved this exact issue. The token is sent only to the
    configured Atlassian site and never appears in errors.

    Raises:
        RuntimeError: if Jira cannot be reached or refuses the issue, with
            Jira's own status and message.
    """
    fields: dict[str, Any] = {
        "project": {"key": issue.project},
        "summary": issue.summary,
        "issuetype": {"name": ISSUE_TYPE},
        "labels": list(issue.labels),
    }
    if issue.body.strip():
        fields["description"] = _document(issue.body)
    try:
        response = client.post(
            f"{access.site}/rest/api/3/issue",
            auth=(access.email, access.api_token),
            headers={"Accept": "application/json"},
            json={"fields": fields},
        )
    except httpx.HTTPError as error:
        # str(error) is not guaranteed to be free of request details, so only the type is kept.
        raise RuntimeError(f"Jira could not be reached ({type(error).__name__})") from None
    if response.status_code != 201:
        raise RuntimeError(
            f"Jira refused to create the issue in {issue.project} "
            f"(HTTP {response.status_code}): {_refusal(response) or 'no details given'}"
        )
    return f"{access.site}/browse/{response.json()['key']}"
