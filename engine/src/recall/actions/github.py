# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The GitHub issue action: validating a request and creating the issue."""

import re
from collections.abc import Collection
from dataclasses import asdict, dataclass
from typing import Any

import httpx

KIND = "github_issue"
"""Action kind under which GitHub issues are stored."""

_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}")
_MAX_TITLE = 256
_MAX_BODY = 10_000
_MAX_LABELS = 10
_MAX_LABEL = 50


@dataclass(frozen=True, slots=True)
class GitHubIssue:
    """A GitHub issue someone wants to create.

    Constructing one validates every field, so an instance is always safe to
    store and to send. ``repo`` is ``owner/name``.

    Raises:
        ValueError: on construction, describing the first invalid field.
    """

    repo: str
    title: str
    body: str = ""
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.repo, str) or not _REPO.fullmatch(self.repo):
            raise ValueError(f"repo must look like 'owner/name', got {self.repo!r}")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must not be empty")
        if len(self.title) > _MAX_TITLE:
            raise ValueError(f"title must be at most {_MAX_TITLE} characters")
        if not isinstance(self.body, str) or len(self.body) > _MAX_BODY:
            raise ValueError(f"body must be text of at most {_MAX_BODY} characters")
        if len(self.labels) > _MAX_LABELS:
            raise ValueError(f"at most {_MAX_LABELS} labels are allowed")
        for label in self.labels:
            if not isinstance(label, str) or not label.strip() or len(label) > _MAX_LABEL:
                raise ValueError(f"each label must be 1-{_MAX_LABEL} characters, got {label!r}")

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON-serialisable form stored with a pending action."""
        return {**asdict(self), "labels": list(self.labels)}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "GitHubIssue":
        """Rebuild (and re-validate) an issue from :meth:`to_payload` output.

        Raises:
            ValueError: if the payload has unknown or invalid fields.
        """
        try:
            return cls(
                repo=payload["repo"],
                title=payload["title"],
                body=payload.get("body", ""),
                labels=tuple(payload.get("labels", ())),
            )
        except (KeyError, TypeError) as error:
            raise ValueError(f"malformed GitHub issue payload: {error}") from error


def require_allowed_repo(issue: GitHubIssue, allowed_repos: Collection[str]) -> None:
    """Refuse an issue aimed at a repository that was not explicitly allowed.

    The allowlist is deny-by-default: with no repositories configured, every
    issue is refused. Comparison ignores case, as GitHub does.

    Raises:
        PermissionError: naming the repository and how to allow it.
    """
    if issue.repo.lower() not in {repo.lower() for repo in allowed_repos}:
        raise PermissionError(
            f"Repository {issue.repo!r} is not allowed. Add it to RECALL_GITHUB_REPOS "
            "(comma-separated owner/name) to permit issues there."
        )


def create_issue(issue: GitHubIssue, token: str, client: httpx.Client) -> str:
    """Create ``issue`` on GitHub and return the new issue's web URL.

    Changes an external system and cannot be undone from here; call it only
    after a human approved this exact issue. The token is sent only to
    GitHub and never appears in errors.

    Raises:
        RuntimeError: if GitHub rejects the request (bad token, no access to
            the repository, issues disabled, rate limit), with GitHub's own
            status and message.
        httpx.HTTPError: if GitHub cannot be reached.
    """
    response = client.post(
        f"https://api.github.com/repos/{issue.repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"title": issue.title, "body": issue.body, "labels": list(issue.labels)},
    )
    if response.status_code != 201:
        try:
            message = response.json().get("message", "")
        except ValueError:
            message = ""
        raise RuntimeError(
            f"GitHub refused to create the issue in {issue.repo} "
            f"(HTTP {response.status_code}): {message or 'no details given'}"
        )
    return str(response.json()["html_url"])
