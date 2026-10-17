# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The Notion action: a meeting's summary saved as a page under one parent page.

The parent page is configured by the user and shared with their Notion
integration; the AI model cannot choose where the page goes. A person
approves every page before it is created.
"""

import re
from dataclasses import dataclass
from typing import Any

import httpx

KIND = "notion_page"
"""Action kind under which Notion pages are stored."""

_PAGES_URL = "https://api.notion.com/v1/pages"
_VERSION = "2022-06-28"
_PAGE_ID = re.compile(r"[0-9a-f]{32}")
_MAX_TITLE = 200
_MAX_BODY = 20_000
_MAX_TEXT = 2000
"""Notion's limit on one rich-text item."""
_MAX_BLOCKS = 100
"""Notion's limit on children sent with a new page."""


@dataclass(frozen=True, slots=True)
class NotionAccess:
    """An internal integration token and the page new pages are created under."""

    token: str
    parent_page_id: str

    def __post_init__(self) -> None:
        if not _PAGE_ID.fullmatch(self.parent_page_id):
            raise ValueError("RECALL_NOTION_PAGE_ID must be a Notion page id (32 hex characters)")

    def __repr__(self) -> str:
        return f"NotionAccess(parent_page_id={self.parent_page_id!r})"


def page_id(raw: str) -> str:
    """Normalise a page id, with or without hyphens, or a Notion page URL to its 32-character id."""
    last = raw.strip().split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return last.replace("-", "").lower()[-32:]


def require_access(access: NotionAccess | None) -> NotionAccess:
    """Return ``access``, or refuse when Notion is not configured.

    Raises:
        PermissionError: if ``NOTION_TOKEN`` or ``RECALL_NOTION_PAGE_ID`` is unset.
    """
    if access is None:
        raise PermissionError("Notion is not configured (set NOTION_TOKEN and RECALL_NOTION_PAGE_ID)")
    return access


@dataclass(frozen=True, slots=True)
class NotionPage:
    """A page with a title and a Markdown body (headings, bullets, to-dos, text).

    Raises:
        ValueError: on construction, describing the first invalid field.
    """

    title: str
    body: str

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip() or len(self.title) > _MAX_TITLE:
            raise ValueError(f"title must be 1-{_MAX_TITLE} characters")
        if not isinstance(self.body, str) or not self.body.strip() or len(self.body) > _MAX_BODY:
            raise ValueError(f"body must be 1-{_MAX_BODY} characters")

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON-serialisable form stored with a pending action."""
        return {"title": self.title, "body": self.body}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "NotionPage":
        """Rebuild (and re-validate) a page from :meth:`to_payload` output.

        Raises:
            ValueError: if the payload is malformed or invalid.
        """
        try:
            return cls(payload["title"], payload["body"])
        except (KeyError, TypeError) as error:
            raise ValueError(f"malformed Notion payload: {error}") from error


def _block(kind: str, text: str, **extra: Any) -> dict[str, Any]:
    rich = [{"type": "text", "text": {"content": text[:_MAX_TEXT]}}]
    return {"object": "block", "type": kind, kind: {"rich_text": rich, **extra}}


def blocks(markdown: str) -> list[dict[str, Any]]:
    """Convert the summary's Markdown into Notion blocks (at most 100)."""
    out: list[dict[str, Any]] = []
    for line in markdown.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            out.append(_block("heading_3", line[4:]))
        elif line.startswith("## "):
            out.append(_block("heading_2", line[3:]))
        elif line.startswith(("- [ ] ", "- [x] ")):
            out.append(_block("to_do", line[6:], checked=line[3] == "x"))
        elif line.startswith("- "):
            out.append(_block("bulleted_list_item", line[2:]))
        else:
            out.append(_block("paragraph", line))
    return out[:_MAX_BLOCKS]


def create_page(page: NotionPage, access: NotionAccess, client: httpx.Client) -> str:
    """Create the page under the configured parent and return its URL.

    Changes an external system; call it only after a human approved this
    exact page.

    Raises:
        RuntimeError: if Notion cannot be reached or refuses the page, with
            Notion's own status and message but never the token.
    """
    body = {
        "parent": {"page_id": access.parent_page_id},
        "properties": {"title": {"title": [{"type": "text", "text": {"content": page.title}}]}},
        "children": blocks(page.body),
    }
    headers = {"Authorization": f"Bearer {access.token}", "Notion-Version": _VERSION}
    try:
        created = client.post(_PAGES_URL, headers=headers, json=body)
    except httpx.HTTPError as error:
        raise RuntimeError(f"Notion could not be reached ({type(error).__name__})") from None
    if created.status_code != 200:
        try:
            message = str(created.json().get("message", ""))[:200]
        except ValueError:
            message = ""
        raise RuntimeError(f"Notion refused the page (HTTP {created.status_code}): {message}")
    return str(created.json().get("url", "Page created"))
