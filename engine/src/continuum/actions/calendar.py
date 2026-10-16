# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The calendar deadline action: an all-day Google Calendar event on a due date."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

KIND = "calendar_deadline"
"""Action kind under which calendar deadlines are stored."""

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar}/events"
_MAX_TITLE = 256
_MAX_DESCRIPTION = 5000


@dataclass(frozen=True, slots=True, repr=False)
class GoogleAccess:
    """OAuth credentials of the user's own Google Cloud client.

    The refresh token must have been granted the
    ``https://www.googleapis.com/auth/calendar.events`` scope. Has no
    ``repr``, so the secrets cannot end up in a log line by accident.
    """

    client_id: str
    client_secret: str
    refresh_token: str


@dataclass(frozen=True, slots=True)
class CalendarDeadline:
    """A deadline someone wants on the calendar, as an all-day event.

    ``due`` is an ISO date (``YYYY-MM-DD``). The calendar it goes to is the
    one the user configured, never chosen by the proposal.

    Raises:
        ValueError: on construction, describing the first invalid field.
    """

    title: str
    due: str
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must not be empty")
        if len(self.title) > _MAX_TITLE:
            raise ValueError(f"title must be at most {_MAX_TITLE} characters")
        try:
            parsed = date.fromisoformat(self.due)
        except (TypeError, ValueError):
            raise ValueError(f"due must be a date like 2026-11-30, got {self.due!r}") from None
        if parsed.isoformat() != self.due:
            raise ValueError(f"due must be a date like 2026-11-30, got {self.due!r}")
        if not isinstance(self.description, str) or len(self.description) > _MAX_DESCRIPTION:
            raise ValueError(f"description must be text of at most {_MAX_DESCRIPTION} characters")

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON-serialisable form stored with a pending action."""
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CalendarDeadline":
        """Rebuild (and re-validate) a deadline from :meth:`to_payload` output.

        Raises:
            ValueError: if the payload is malformed or invalid.
        """
        try:
            return cls(
                title=payload["title"],
                due=payload["due"],
                description=payload.get("description", ""),
            )
        except (KeyError, TypeError) as error:
            raise ValueError(f"malformed calendar deadline payload: {error}") from error


def require_access(access: GoogleAccess | None) -> GoogleAccess:
    """Return the configured Google credentials or refuse.

    Raises:
        PermissionError: if Google Calendar is not configured.
    """
    if access is None:
        raise PermissionError(
            "Google Calendar is not configured. Set GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN to permit deadlines."
        )
    return access


def _google_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return "no details given"
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return str(error.get("message", "no details given"))
    return str(body.get("error_description") or error or "no details given")


def _access_token(access: GoogleAccess, client: httpx.Client) -> str:
    """Exchange the refresh token for a short-lived access token.

    Raises:
        RuntimeError: if Google rejects the credentials.
        httpx.HTTPError: if Google cannot be reached.
    """
    granted = client.post(
        _TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": access.client_id,
            "client_secret": access.client_secret,
            "refresh_token": access.refresh_token,
        },
    )
    if granted.status_code != 200:
        raise RuntimeError(
            "Google rejected the calendar credentials "
            f"(HTTP {granted.status_code}): {_google_error(granted)}"
        )
    return str(granted.json()["access_token"])


def current_event_title(
    access: GoogleAccess, calendar_id: str, client: httpx.Client, now: datetime
) -> str | None:
    """Title of the timed event happening at ``now`` (``now`` timezone-aware), if any.

    Read-only. All-day events are ignored. Returns ``None`` when nothing is on
    or Google cannot answer, so a meeting can always start without a title.
    """
    window_end = now + timedelta(minutes=1)
    try:
        token = _access_token(access, client)
        response = client.get(
            _EVENTS_URL.format(calendar=quote(calendar_id, safe="")),
            headers={"Authorization": f"Bearer {token}"},
            params={
                "timeMin": now.isoformat(),
                "timeMax": window_end.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": "5",
            },
        )
    except (httpx.HTTPError, RuntimeError):
        return None
    if response.status_code != 200:
        return None
    try:
        items = response.json().get("items", [])
    except ValueError:
        return None
    for item in items:
        if isinstance(item, dict) and "dateTime" in item.get("start", {}):
            title = " ".join(str(item.get("summary", "")).split())
            if title:
                return title[:120]
    return None


# ponytail: the refresh token must be obtained once outside this app (for
# example with Google's OAuth playground). Add an in-app consent flow when
# more than one person uses this.
def create_deadline(
    deadline: CalendarDeadline, access: GoogleAccess, calendar_id: str, client: httpx.Client
) -> str:
    """Create the all-day event and return its web link.

    Changes an external system; call it only after a human approved this
    exact deadline. Secrets are sent only to Google and never appear in
    errors.

    Raises:
        RuntimeError: if Google cannot be reached, rejects the credentials,
            or refuses the event, with Google's own status and message.
    """
    try:
        token = _access_token(access, client)
        day = date.fromisoformat(deadline.due)
        created = client.post(
            _EVENTS_URL.format(calendar=quote(calendar_id, safe="")),
            headers={"Authorization": f"Bearer {token}"},
            json={
                "summary": deadline.title,
                "description": deadline.description,
                "start": {"date": day.isoformat()},
                "end": {"date": (day + timedelta(days=1)).isoformat()},
            },
        )
    except httpx.HTTPError as error:
        raise RuntimeError(f"Google could not be reached ({type(error).__name__})") from None
    if created.status_code != 200:
        raise RuntimeError(
            f"Google refused the event (HTTP {created.status_code}): {_google_error(created)}"
        )
    return str(created.json().get("htmlLink", "Created in Google Calendar"))
