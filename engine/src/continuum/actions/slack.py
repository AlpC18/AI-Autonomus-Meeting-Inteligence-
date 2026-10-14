# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The Slack message action: validating a message and posting it to a webhook."""

from dataclasses import dataclass
from typing import Any

import httpx

KIND = "slack_message"
"""Action kind under which Slack messages are stored."""

WEBHOOK_PREFIX = "https://hooks.slack.com/"
"""Only Slack's own incoming-webhook host is ever contacted."""

_MAX_TEXT = 3000


@dataclass(frozen=True, slots=True)
class SlackMessage:
    """A message someone wants to post to the configured Slack channel.

    The destination is not part of the message: it is the one webhook the
    user configured, so a proposal can never choose where it is sent.

    Raises:
        ValueError: on construction, if ``text`` is empty or too long.
    """

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("text must not be empty")
        if len(self.text) > _MAX_TEXT:
            raise ValueError(f"text must be at most {_MAX_TEXT} characters")

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON-serialisable form stored with a pending action."""
        return {"text": self.text}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SlackMessage":
        """Rebuild (and re-validate) a message from :meth:`to_payload` output.

        Raises:
            ValueError: if the payload is malformed or invalid.
        """
        try:
            return cls(text=payload["text"])
        except (KeyError, TypeError) as error:
            raise ValueError(f"malformed Slack message payload: {error}") from error


def require_webhook(webhook_url: str | None) -> str:
    """Return the configured webhook URL, refusing a missing or foreign one.

    Raises:
        PermissionError: if no webhook is configured or it does not point at
            Slack. The URL itself is a secret and is never included.
    """
    if not webhook_url:
        raise PermissionError(
            "Slack is not configured. Set CONTINUUM_SLACK_WEBHOOK_URL to an "
            "incoming-webhook URL to permit messages."
        )
    if not webhook_url.startswith(WEBHOOK_PREFIX):
        raise PermissionError(f"CONTINUUM_SLACK_WEBHOOK_URL must start with {WEBHOOK_PREFIX}")
    return webhook_url


def send_message(message: SlackMessage, webhook_url: str, client: httpx.Client) -> str:
    """Post ``message`` to the Slack webhook and return a short confirmation.

    Changes an external system and cannot be undone from here; call it only
    after a human approved this exact message. The webhook URL is a secret
    and never appears in errors.

    Raises:
        RuntimeError: if Slack cannot be reached or refuses the message.
    """
    try:
        response = client.post(require_webhook(webhook_url), json={"text": message.text})
    except httpx.HTTPError as error:
        # str(error) can contain the webhook URL, so only the error type is kept.
        raise RuntimeError(f"Slack could not be reached ({type(error).__name__})") from None
    if response.status_code != 200:
        raise RuntimeError(
            f"Slack refused the message (HTTP {response.status_code}): {response.text[:200]}"
        )
    return "Posted to Slack"
