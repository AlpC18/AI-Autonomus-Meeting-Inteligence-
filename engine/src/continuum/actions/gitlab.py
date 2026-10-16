# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The GitLab issue action: validating a request and creating the issue.

Works with gitlab.com and self-managed GitLab over HTTPS. A project is named
by its path (``group/subgroup/name``).
"""

import re
from collections.abc import Collection
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote

import httpx

KIND = "gitlab_issue"
"""Action kind under which GitLab issues are stored."""

DEFAULT_URL = "https://gitlab.com"

_URL = re.compile(r"https://[A-Za-z0-9.-]+(?::\d{1,5})?(?:/[A-Za-z0-9._~-]+)*")
_PROJECT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,254}(?:/[A-Za-z0-9_][A-Za-z0-9_.-]{0,254}){1,19}")
_MAX_TITLE = 255
_MAX_BODY = 10_000
_MAX_LABELS = 10
_MAX_LABEL = 50


@dataclass(frozen=True, slots=True, repr=False)
class GitLabAccess:
    """A GitLab instance and a personal access token for it.

    Only ``https://`` URLs are accepted, so the token never travels in clear
    text. Has no ``repr``, so the token cannot end up in a log line.

    Raises:
        ValueError: on construction, if ``url`` is not an HTTPS URL.
    """

    url: str
    token: str

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not _URL.fullmatch(self.url):
            raise ValueError("GitLab URL must look like https://gitlab.com or https://gitlab.example.com")

    def api(self, path: str) -> str:
        """The REST URL of ``path`` (starting with ``/``) on this instance."""
        return f"{self.url}/api/v4{path}"

    @property
    def headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self.token}


def project_path(project: str) -> str:
    """``project`` encoded as one URL segment, as GitLab's API expects."""
    return quote(project, safe="")


@dataclass(frozen=True, slots=True)
class GitLabIssue:
    """A GitLab issue someone wants to create in ``project`` (``group/name``).

    Raises:
        ValueError: on construction, describing the first invalid field.
    """

    project: str
    title: str
    body: str = ""
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.project, str) or not _PROJECT.fullmatch(self.project):
            raise ValueError(f"project must look like 'group/name', got {self.project!r}")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must not be empty")
        if len(self.title) > _MAX_TITLE:
            raise ValueError(f"title must be at most {_MAX_TITLE} characters")
        if not isinstance(self.body, str) or len(self.body) > _MAX_BODY:
            raise ValueError(f"body must be text of at most {_MAX_BODY} characters")
        if len(self.labels) > _MAX_LABELS:
            raise ValueError(f"at most {_MAX_LABELS} labels are allowed")
        for label in self.labels:
            # GitLab separates labels with commas, so a comma would make two.
            if not isinstance(label, str) or not label.strip() or len(label) > _MAX_LABEL or "," in label:
                raise ValueError(f"each label must be 1-{_MAX_LABEL} characters without commas, got {label!r}")

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON-serialisable form stored with a pending action."""
        return {**asdict(self), "labels": list(self.labels)}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "GitLabIssue":
        """Rebuild (and re-validate) an issue from :meth:`to_payload` output.

        Raises:
            ValueError: if the payload has unknown or invalid fields.
        """
        try:
            return cls(
                project=payload["project"],
                title=payload["title"],
                body=payload.get("body", ""),
                labels=tuple(payload.get("labels", ())),
            )
        except (KeyError, TypeError) as error:
            raise ValueError(f"malformed GitLab issue payload: {error}") from error


def require_access(access: GitLabAccess | None) -> GitLabAccess:
    """Return the configured GitLab access, refusing when there is none.

    Raises:
        PermissionError: naming the variables that enable GitLab.
    """
    if access is None:
        raise PermissionError("GitLab is not configured. Set GITLAB_TOKEN (and CONTINUUM_GITLAB_URL if self-managed).")
    return access


def require_allowed_project(issue: GitLabIssue, allowed_projects: Collection[str]) -> None:
    """Refuse an issue aimed at a project that was not explicitly allowed (deny by default).

    Raises:
        PermissionError: naming the project and how to allow it.
    """
    if issue.project.lower() not in {project.lower() for project in allowed_projects}:
        raise PermissionError(
            f"Project {issue.project!r} is not allowed. Add it to CONTINUUM_GITLAB_PROJECTS "
            "(comma-separated group/name) to permit issues there."
        )


def create_issue(issue: GitLabIssue, access: GitLabAccess, client: httpx.Client) -> str:
    """Create ``issue`` on GitLab and return the new issue's web URL.

    Changes an external system; call it only after a human approved this
    exact issue. The token never appears in errors.

    Raises:
        RuntimeError: if GitLab rejects the request, with its status and message.
        httpx.HTTPError: if GitLab cannot be reached.
    """
    response = client.post(
        access.api(f"/projects/{project_path(issue.project)}/issues"),
        headers=access.headers,
        json={"title": issue.title, "description": issue.body, "labels": ",".join(issue.labels)},
    )
    if response.status_code != 201:
        try:
            message = str(response.json().get("message", ""))
        except (ValueError, AttributeError):
            message = ""
        raise RuntimeError(
            f"GitLab refused to create the issue in {issue.project} "
            f"(HTTP {response.status_code}): {message or 'no details given'}"
        )
    return str(response.json()["web_url"])
