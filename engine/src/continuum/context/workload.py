# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""A speaker's open Jira issues, for checking the dates they promise.

Read-only: it counts issues and never changes anything. The local user
("me") is Jira's current user; another speaker is looked up by the name the
user gave them, and only an unambiguous, active match is used.
"""

import json
import logging
from datetime import date

import httpx

from continuum.actions.jira import JiraAccess
from continuum.context.risk import Workload

logger = logging.getLogger(__name__)

ME = "me"
"""Speaker label of the local user (the microphone)."""


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
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            logger.warning("Could not read the Jira workload (%s)", type(error).__name__)
            return None

    def _assignee(self, speaker: str) -> str | None:
        """A JQL assignee for ``speaker``; ``None`` for unnamed speakers or no single match."""
        if speaker == ME:
            return "currentUser()"
        if speaker.startswith("Speaker ") or speaker == "others":
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

    def _count(self, jql: str) -> int:
        response = self._client.post(
            f"{self._access.site}/rest/api/3/search/approximate-count",
            json={"jql": jql},
            auth=(self._access.email, self._access.api_token),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return int(response.json()["count"])
