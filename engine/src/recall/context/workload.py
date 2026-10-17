# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""A speaker's open Jira, GitHub and GitLab issues, for checking the dates they promise.

Read-only: it counts issues and never changes anything. The local user
("me") is the tracker's current user; another speaker is looked up by the
name the user gave them, and only an unambiguous match is used.
"""

import json
import logging
from collections.abc import Sequence
from datetime import date, datetime

import httpx

from recall.actions.gitlab import GitLabAccess, project_path
from recall.actions.jira import JiraAccess
from recall.context.risk import Workload, WorkloadLookup

logger = logging.getLogger(__name__)

ME = "me"
"""Speaker label of the local user (the microphone)."""

MAX_PAGES = 50
"""Pages of 100 read per list (5,000 issues or members), so one huge backlog cannot stall a meeting."""


def _all_pages(client: httpx.Client, url: str, params: dict[str, object], headers: dict[str, str]) -> list:
    """Every item of a paginated GitHub or GitLab list, following its ``Link: rel="next"`` header.

    Raises:
        httpx.HTTPStatusError: if a page is refused.
    """
    items: list = []
    next_url: str | None = url
    for page in range(MAX_PAGES):
        response = client.get(next_url, params={**params, "per_page": 100} if page == 0 else None, headers=headers)
        response.raise_for_status()
        items += response.json()
        next_url = response.links.get("next", {}).get("url")
        if next_url is None:
            return items
    logger.warning("Read only the first %d items of %s", len(items), url)
    return items


class JiraWorkload:
    """``(speaker, due) -> Workload`` from Jira Cloud. Blocks; errors give ``None``."""

    def __init__(self, access: JiraAccess, client: httpx.Client) -> None:
        self._access = access
        self._client = client
        self._accounts: dict[str, str | None] = {}

    def __call__(self, speaker: str, due: date) -> Workload | None:
        try:
            assignee = self._assignee(speaker)
            if assignee is None:
                return None
            open_jql = f"assignee = {assignee} AND statusCategory != Done"
            return Workload(
                open=self._count(open_jql),
                due_by=self._count(f'{open_jql} AND duedate <= "{due.isoformat()}"'),
                source="Jira",
                sprint=self._sprint(open_jql),
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            logger.warning("Could not read the Jira workload (%s)", type(error).__name__)
            return None

    def _assignee(self, speaker: str) -> str | None:
        """A JQL assignee for ``speaker``; ``None`` for unnamed speakers or no single match."""
        if speaker == ME:
            return "currentUser()"
        if _unnamed(speaker):
            return None
        if speaker not in self._accounts:
            response = self._client.get(
                f"{self._access.site}/rest/api/3/user/search",
                params={"query": speaker},
                auth=(self._access.email, self._access.api_token),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            active = [user["accountId"] for user in response.json() if user.get("active")]
            self._accounts[speaker] = active[0] if len(active) == 1 else None
        account = self._accounts[speaker]
        # json.dumps quotes the id, so it cannot break out of the JQL string.
        return json.dumps(account) if account else None

    def _sprint(self, open_jql: str) -> int:
        """Open issues in an active sprint; 0 on sites without Jira Software sprints."""
        try:
            return self._count(f"{open_jql} AND sprint in openSprints()")
        except httpx.HTTPStatusError:
            return 0

    def _count(self, jql: str) -> int:
        response = self._client.post(
            f"{self._access.site}/rest/api/3/search/approximate-count",
            json={"jql": jql},
            auth=(self._access.email, self._access.api_token),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return int(response.json()["count"])


def _unnamed(speaker: str) -> bool:
    return speaker.startswith("Speaker ") or speaker == "others"


class GitHubWorkload:
    """``(speaker, due) -> Workload`` from open GitHub issues in ``repos``. Blocks; errors give ``None``.

    GitHub issues have no due date, so an issue counts as due by the promised
    date when its milestone is. Another speaker is matched, by login or
    profile name, only among the people who can be assigned in ``repos``.
    """

    def __init__(self, token: str, repos: Sequence[str], client: httpx.Client) -> None:
        self._repos = tuple(sorted(repos))
        self._client = client
        self._headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        self._logins: dict[str, str | None] = {}
        self._names: dict[str, str] = {}

    def __call__(self, speaker: str, due: date) -> Workload | None:
        try:
            login = self._login(speaker)
            if login is None:
                return None
            issues = [
                issue
                for repo in self._repos
                for issue in self._list(f"/repos/{repo}/issues", assignee=login, state="open")
                if "pull_request" not in issue
            ]
            due_by = sum(
                1
                for issue in issues
                if (issue.get("milestone") or {}).get("due_on")
                and datetime.fromisoformat(issue["milestone"]["due_on"]).date() <= due
            )
            return Workload(open=len(issues), due_by=due_by, source="GitHub")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            logger.warning("Could not read the GitHub workload (%s)", type(error).__name__)
            return None

    def _get(self, path: str) -> dict:
        response = self._client.get(f"https://api.github.com{path}", headers=self._headers)
        response.raise_for_status()
        return response.json()

    def _list(self, path: str, **params: object) -> list:
        return _all_pages(self._client, f"https://api.github.com{path}", params, self._headers)

    def _login(self, speaker: str) -> str | None:
        if _unnamed(speaker):
            return None
        if speaker not in self._logins:
            self._logins[speaker] = self._find_login(speaker)
        return self._logins[speaker]

    def _find_login(self, speaker: str) -> str | None:
        if speaker == ME:
            return str(self._get("/user")["login"])
        wanted = speaker.casefold()
        logins = {user["login"] for repo in self._repos for user in self._list(f"/repos/{repo}/assignees")}
        matches = [login for login in sorted(logins) if login.casefold() == wanted]
        if not matches:
            matches = [login for login in sorted(logins) if self._name(login).casefold() == wanted]
        return matches[0] if len(matches) == 1 else None


    def _name(self, login: str) -> str:
        if login not in self._names:
            self._names[login] = str(self._get(f"/users/{login}").get("name") or "")
        return self._names[login]


class GitLabWorkload:
    """``(speaker, due) -> Workload`` from open GitLab issues in ``projects``. Blocks; errors give ``None``.

    An issue is due by the promised date when its own due date, or else its
    milestone's, is. Another speaker is matched, by username or name, only
    among the projects' members.
    """

    def __init__(self, access: GitLabAccess, projects: Sequence[str], client: httpx.Client) -> None:
        self._access = access
        self._projects = tuple(sorted(projects))
        self._client = client
        self._usernames: dict[str, str | None] = {}

    def __call__(self, speaker: str, due: date) -> Workload | None:
        try:
            username = self._username(speaker)
            if username is None:
                return None
            issues = [
                issue
                for project in self._projects
                for issue in self._list(
                    f"/projects/{project_path(project)}/issues", assignee_username=username, state="opened"
                )
            ]
            due_by = sum(1 for issue in issues if (day := _gitlab_due(issue)) is not None and day <= due)
            return Workload(open=len(issues), due_by=due_by, source="GitLab")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            logger.warning("Could not read the GitLab workload (%s)", type(error).__name__)
            return None

    def _get(self, path: str) -> dict:
        response = self._client.get(self._access.api(path), headers=self._access.headers)
        response.raise_for_status()
        return response.json()

    def _list(self, path: str, **params: object) -> list:
        return _all_pages(self._client, self._access.api(path), params, self._access.headers)

    def _username(self, speaker: str) -> str | None:
        if _unnamed(speaker):
            return None
        if speaker not in self._usernames:
            self._usernames[speaker] = self._find_username(speaker)
        return self._usernames[speaker]

    def _find_username(self, speaker: str) -> str | None:
        if speaker == ME:
            return str(self._get("/user")["username"])
        wanted = speaker.casefold()
        members = {
            member["username"]: str(member.get("name") or "")
            for project in self._projects
            for member in self._list(f"/projects/{project_path(project)}/members/all")
        }
        matches = sorted(name for name in members if name.casefold() == wanted) or sorted(
            name for name, full in members.items() if full.casefold() == wanted
        )
        return matches[0] if len(matches) == 1 else None


def _gitlab_due(issue: dict) -> date | None:
    raw = issue.get("due_date") or (issue.get("milestone") or {}).get("due_date")
    return date.fromisoformat(raw) if raw else None


def combined(lookups: Sequence[WorkloadLookup]) -> WorkloadLookup:
    """One lookup adding up the workloads of several trackers; ``None`` if none knows the speaker."""

    def lookup(speaker: str, due: date) -> Workload | None:
        found = [load for each in lookups if (load := each(speaker, due)) is not None]
        if not found:
            return None
        return Workload(
            open=sum(load.open for load in found),
            due_by=sum(load.due_by for load in found),
            source=" and ".join(load.source for load in found),
            sprint=sum(load.sprint for load in found),
        )

    return lookup
