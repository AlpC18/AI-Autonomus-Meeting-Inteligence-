# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The recap e-mail action: the meeting summary sent from the user's Gmail.

Recipients come from the calendar event, never from the AI model, and a
person approves every e-mail before it is sent. The Google refresh token
must also have been granted ``https://www.googleapis.com/auth/gmail.send``.
"""

import base64
import re
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

import httpx

from continuum.actions.calendar import GoogleAccess, _access_token, _google_error

KIND = "email_recap"
"""Action kind under which recap e-mails are stored."""

_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
_ADDRESS = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+")
MAX_RECIPIENTS = 50
_MAX_SUBJECT = 200
_MAX_BODY = 20_000


@dataclass(frozen=True, slots=True)
class EmailRecap:
    """A plain-text e-mail to the meeting's attendees.

    Raises:
        ValueError: on construction, describing the first invalid field.
    """

    to: tuple[str, ...]
    subject: str
    body: str

    def __post_init__(self) -> None:
        if not isinstance(self.to, tuple) or not 0 < len(self.to) <= MAX_RECIPIENTS:
            raise ValueError(f"an e-mail needs 1-{MAX_RECIPIENTS} recipients (the meeting's attendees)")
        bad = [address for address in self.to if not isinstance(address, str) or not _ADDRESS.fullmatch(address)]
        if bad:
            raise ValueError(f"not an e-mail address: {bad[0]!r}")
        if not isinstance(self.subject, str) or not self.subject.strip() or len(self.subject) > _MAX_SUBJECT:
            raise ValueError(f"subject must be 1-{_MAX_SUBJECT} characters")
        if "\n" in self.subject or "\r" in self.subject:
            raise ValueError("subject must be one line")
        if not isinstance(self.body, str) or not self.body.strip() or len(self.body) > _MAX_BODY:
            raise ValueError(f"body must be 1-{_MAX_BODY} characters")

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON-serialisable form stored with a pending action."""
        return {"to": list(self.to), "subject": self.subject, "body": self.body}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "EmailRecap":
        """Rebuild (and re-validate) an e-mail from :meth:`to_payload` output.

        Raises:
            ValueError: if the payload is malformed or invalid.
        """
        try:
            to = payload["to"]
            if not isinstance(to, list):
                raise TypeError("to must be a list")
            return cls(tuple(to), payload["subject"], payload["body"])
        except (KeyError, TypeError) as error:
            raise ValueError(f"malformed e-mail payload: {error}") from error


def send(recap: EmailRecap, access: GoogleAccess, client: httpx.Client) -> str:
    """Send the e-mail from the user's Gmail and return a confirmation.

    Changes an external system; call it only after a human approved this
    exact e-mail.

    Raises:
        RuntimeError: if Google cannot be reached, rejects the credentials,
            or refuses the message, with Google's own status and message.
    """
    message = EmailMessage()
    message["To"] = ", ".join(recap.to)
    message["Subject"] = recap.subject
    message.set_content(recap.body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    try:
        token = _access_token(access, client)
        sent = client.post(_SEND_URL, headers={"Authorization": f"Bearer {token}"}, json={"raw": raw})
    except httpx.HTTPError as error:
        raise RuntimeError(f"Google could not be reached ({type(error).__name__})") from None
    if sent.status_code != 200:
        raise RuntimeError(f"Gmail refused the e-mail (HTTP {sent.status_code}): {_google_error(sent)}")
    return f"Sent to {len(recap.to)} attendee(s)"
