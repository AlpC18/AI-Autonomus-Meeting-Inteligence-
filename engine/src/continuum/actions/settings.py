# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Settings of the action engine, read from environment variables."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from continuum.actions.calendar import GoogleAccess
from continuum.actions.jira import JiraAccess
from continuum.actions.notion import NotionAccess, page_id


@dataclass(frozen=True, slots=True)
class ActionSettings:
    """Where actions are queued and what they are allowed to touch.

    ``github_repos`` is the allowlist of ``owner/name`` repositories; empty
    means no GitHub issue may be proposed or created. ``github_token`` is
    needed only to execute an approved action, never to propose one.
    ``slack_webhook_url`` is the single Slack destination and ``google`` the
    credentials for ``google_calendar_id``. ``jira`` is the Jira Cloud access
    and ``jira_projects`` the allowlist of project keys. ``notion`` is the
    integration token and the one parent page meeting pages go under. A
    connector left unset accepts no proposals at all.
    """

    database: Path = Path.home() / ".continuum" / "actions.db"
    github_repos: frozenset[str] = frozenset()
    github_token: str | None = None
    slack_webhook_url: str | None = None
    google: GoogleAccess | None = None
    google_calendar_id: str = "primary"
    jira: JiraAccess | None = None
    jira_projects: frozenset[str] = frozenset()
    notion: NotionAccess | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "ActionSettings":
        """Read the action settings from ``env``.

        Variables: ``CONTINUUM_ACTIONS_DB``, ``CONTINUUM_GITHUB_REPOS``
        (comma-separated), ``GITHUB_TOKEN``, ``CONTINUUM_SLACK_WEBHOOK_URL``,
        ``GOOGLE_CLIENT_ID``, ``GOOGLE_CLIENT_SECRET``, ``GOOGLE_REFRESH_TOKEN``,
        ``CONTINUUM_GOOGLE_CALENDAR_ID``, ``CONTINUUM_JIRA_SITE``, ``JIRA_EMAIL``,
        ``JIRA_API_TOKEN``, ``CONTINUUM_JIRA_PROJECTS`` (comma-separated
        keys), ``NOTION_TOKEN`` and ``CONTINUUM_NOTION_PAGE_ID`` (an id or the
        page's URL). Google, Jira and Notion access each need all their
        values; with any missing that connector is off.

        Raises:
            ValueError: if ``CONTINUUM_JIRA_SITE`` is not an Atlassian Cloud site
                or ``CONTINUUM_NOTION_PAGE_ID`` is not a page id.
        """
        database = env.get("CONTINUUM_ACTIONS_DB")
        repos = env.get("CONTINUUM_GITHUB_REPOS", "")
        google = (
            env.get("GOOGLE_CLIENT_ID"),
            env.get("GOOGLE_CLIENT_SECRET"),
            env.get("GOOGLE_REFRESH_TOKEN"),
        )
        jira = (
            env.get("CONTINUUM_JIRA_SITE", "").rstrip("/"),
            env.get("JIRA_EMAIL"),
            env.get("JIRA_API_TOKEN"),
        )
        projects = env.get("CONTINUUM_JIRA_PROJECTS", "")
        notion = (env.get("NOTION_TOKEN"), env.get("CONTINUUM_NOTION_PAGE_ID"))
        return cls(
            database=Path(database) if database else cls().database,
            github_repos=frozenset(part.strip() for part in repos.split(",") if part.strip()),
            github_token=env.get("GITHUB_TOKEN") or None,
            slack_webhook_url=env.get("CONTINUUM_SLACK_WEBHOOK_URL") or None,
            google=GoogleAccess(*google) if all(google) else None,
            google_calendar_id=env.get("CONTINUUM_GOOGLE_CALENDAR_ID") or "primary",
            jira=JiraAccess(*jira) if all(jira) else None,
            jira_projects=frozenset(
                part.strip().upper() for part in projects.split(",") if part.strip()
            ),
            notion=NotionAccess(notion[0], page_id(notion[1])) if all(notion) else None,
        )
