# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Tries every configured outside service once, so a wrong token shows up before a meeting.

Each check is read-only (who am I, can I see this repository), except the
AI provider, which is asked for a one-word reply. Slack webhooks cannot be
checked without posting, so they are only reported as configured.
"""

import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from urllib.parse import quote

import httpx

from continuum import net
from continuum.actions.calendar import _access_token
from continuum.actions.gitlab import project_path
from continuum.actions.settings import ActionSettings
from continuum.llm import Llm, LlmSettings, connect


@dataclass(frozen=True, slots=True)
class Result:
    """How one service answered; ``ok`` is ``None`` when it could not be checked."""

    service: str
    ok: bool | None
    detail: str


class _Refused(Exception):
    pass


def _get(client: httpx.Client, url: str, **kwargs: object) -> dict:
    """GET ``url`` and return its JSON object.

    Raises:
        _Refused: with the status and the service's own message, never the token.
    """
    response = client.get(url, **kwargs)  # type: ignore[arg-type]
    if response.status_code != 200:
        try:
            body = response.json()
            message = body.get("message") or body.get("error") or body.get("errorMessages") or ""
        except (ValueError, AttributeError):
            message = ""
        raise _Refused(f"HTTP {response.status_code}{': ' + str(message)[:200] if message else ''}")
    body = response.json()
    return body if isinstance(body, dict) else {}


def _github(token: str, repos: frozenset[str], client: httpx.Client) -> str:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    login = _get(client, "https://api.github.com/user", headers=headers).get("login", "?")
    for repo in sorted(repos):
        try:
            _get(client, f"https://api.github.com/repos/{repo}", headers=headers)
        except _Refused as error:
            raise _Refused(f"signed in as {login}, but cannot see {repo} ({error})") from None
    return f"signed in as {login}" + (f"; sees {len(repos)} repositories" if repos else "")


def _gitlab(settings: ActionSettings, client: httpx.Client) -> str:
    access = settings.gitlab
    assert access is not None
    user = _get(client, access.api("/user"), headers=access.headers).get("username", "?")
    for project in sorted(settings.gitlab_projects):
        try:
            _get(client, access.api(f"/projects/{project_path(project)}"), headers=access.headers)
        except _Refused as error:
            raise _Refused(f"signed in as {user}, but cannot see {project} ({error})") from None
    return f"signed in as {user}"


def _jira(settings: ActionSettings, client: httpx.Client) -> str:
    access = settings.jira
    assert access is not None
    auth = (access.email, access.api_token)
    headers = {"Accept": "application/json"}
    name = _get(client, f"{access.site}/rest/api/3/myself", auth=auth, headers=headers).get("displayName", "?")
    for key in sorted(settings.jira_projects):
        try:
            _get(client, f"{access.site}/rest/api/3/project/{quote(key)}", auth=auth, headers=headers)
        except _Refused as error:
            raise _Refused(f"signed in as {name}, but cannot see project {key} ({error})") from None
    return f"signed in as {name}"


def _notion(settings: ActionSettings, client: httpx.Client) -> str:
    access = settings.notion
    assert access is not None
    headers = {"Authorization": f"Bearer {access.token}", "Notion-Version": "2022-06-28"}
    try:
        _get(client, f"https://api.notion.com/v1/pages/{access.parent_page_id}", headers=headers)
    except _Refused as error:
        raise _Refused(f"cannot open the parent page; share it with the integration ({error})") from None
    return "can write under the parent page"


def _google(settings: ActionSettings, client: httpx.Client) -> str:
    assert settings.google is not None
    try:
        _access_token(settings.google, client)
    except RuntimeError as error:
        raise _Refused(str(error)) from None
    return "signed in"


def _hugging_face(token: str, client: httpx.Client) -> str:
    who = _get(client, "https://huggingface.co/api/whoami-v2", headers={"Authorization": f"Bearer {token}"})
    return f"signed in as {who.get('name', '?')}"


def _ai(settings: LlmSettings, connector: Callable[[LlmSettings], Llm]) -> str:
    try:
        connector(settings).complete("Reply with the single word OK.", "Are you there?")
    except RuntimeError as error:
        raise _Refused(str(error)) from None
    return f"{settings.model} answered"


def check(
    env: Mapping[str, str], client: httpx.Client, connector: Callable[[LlmSettings], Llm] = connect
) -> list[Result]:
    """Check every service configured in ``env``; unconfigured ones are left out."""
    try:
        actions = ActionSettings.from_env(env)
    except ValueError as error:
        return [Result("Settings", False, str(error))]
    try:
        llm = LlmSettings.from_env(env)
    except ValueError as error:
        return [Result("AI provider", False, str(error))]
    checks: list[tuple[str, Callable[[], str]]] = []
    if llm is not None:
        checks.append((f"AI provider ({llm.provider})", lambda: _ai(llm, connector)))
    if actions.github_token:
        checks.append(("GitHub", lambda: _github(actions.github_token or "", actions.github_repos, client)))
    if actions.gitlab is not None:
        checks.append(("GitLab", lambda: _gitlab(actions, client)))
    if actions.jira is not None:
        checks.append(("Jira", lambda: _jira(actions, client)))
    if actions.notion is not None:
        checks.append(("Notion", lambda: _notion(actions, client)))
    if actions.google is not None:
        checks.append(("Google", lambda: _google(actions, client)))
    if env.get("HF_TOKEN"):
        checks.append(("Hugging Face", lambda: _hugging_face(env["HF_TOKEN"], client)))
    results = []
    for service, run in checks:
        try:
            results.append(Result(service, True, run()))
        except _Refused as error:
            results.append(Result(service, False, str(error)))
        except httpx.HTTPError as error:
            results.append(Result(service, False, f"could not be reached ({type(error).__name__})"))
    if actions.slack_webhook_url:
        results.append(Result("Slack", None, "configured; checked only when a message is approved"))
    return results


def main() -> None:
    """Entry point of ``continuum-check-connections``: prints ``{"results": [...]}``; exit 1 on any failure."""
    with net.client(15) as client:
        results = check(os.environ, client)
    sys.stdout.write(json.dumps({"results": [asdict(result) for result in results]}) + "\n")
    if any(result.ok is False for result in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
