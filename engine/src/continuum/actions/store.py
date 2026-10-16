# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Durable queue of proposed actions and the record of what happened to them.

Rows are never deleted or edited apart from their status, so the table doubles
as the audit log: what was proposed, the exact content, who decided, and the
outcome.
"""

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_PENDING = 50
"""Proposals waiting for a decision at once; more are refused, so a runaway
or manipulated model cannot flood the reviewer."""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'executing', 'done', 'failed', 'rejected')),
    created_at TEXT NOT NULL,
    decided_at TEXT,
    result TEXT
)
"""


@dataclass(frozen=True, slots=True)
class Action:
    """One proposed action and its current state.

    ``status`` is ``pending`` until a human decides, then ``executing`` while
    it runs, and finally ``done``, ``failed`` or ``rejected``. ``result`` holds
    the outcome (for example the created issue's URL, or the error).
    """

    id: str
    kind: str
    payload: dict[str, Any]
    payload_sha256: str
    status: str
    created_at: datetime
    decided_at: datetime | None
    result: str | None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _digest(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode()).hexdigest()


class ActionStore:
    """SQLite-backed store shared by the MCP server and the reviewer.

    Safe to open from several processes at once. Each method opens its own
    short-lived connection, so instances can be used from any thread.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def propose(self, kind: str, payload: dict[str, Any]) -> Action:
        """Queue an action for human review and return it. Nothing is executed.

        Raises:
            RuntimeError: if :data:`MAX_PENDING` proposals are already waiting.
        """
        payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        action_id = uuid.uuid4().hex
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            (pending,) = connection.execute(
                "SELECT COUNT(*) FROM actions WHERE status = 'pending'"
            ).fetchone()
            if pending >= MAX_PENDING:
                raise RuntimeError(
                    f"{MAX_PENDING} actions are already waiting for review; "
                    "approve or reject some before proposing more."
                )
            connection.execute(
                "INSERT INTO actions (id, kind, payload, payload_sha256, status, created_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?)",
                (action_id, kind, payload_json, _digest(payload_json), _now()),
            )
        return self.get(action_id)

    def get(self, action_id: str) -> Action:
        """Return one action.

        Raises:
            KeyError: if no action has this id.
            ValueError: if the stored content no longer matches its checksum,
                meaning the database was altered after the proposal.
        """
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        if row is None:
            raise KeyError(f"no action with id {action_id!r}")
        return self._to_action(row)

    def pending(self) -> list[Action]:
        """Return the actions waiting for a decision, oldest first."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM actions WHERE status = 'pending' ORDER BY created_at"
            ).fetchall()
        return [self._to_action(row) for row in rows]

    def claim(self, action_id: str) -> Action:
        """Move a pending action to ``executing`` and return it.

        This is the single-use gate: only one caller can ever claim an action,
        so an approval cannot be replayed or run twice concurrently.

        Raises:
            KeyError: if no action has this id.
            RuntimeError: if the action is not pending any more.
        """
        return self._transition(action_id, "pending", "executing", None)

    def reject(self, action_id: str) -> Action:
        """Mark a pending action as rejected. Raises like :meth:`claim`."""
        return self._transition(action_id, "pending", "rejected", None)

    def finish(self, action_id: str, *, succeeded: bool, result: str) -> Action:
        """Record the outcome of an action that was claimed.

        Raises:
            KeyError: if no action has this id.
            RuntimeError: if the action is not currently executing.
        """
        return self._transition(
            action_id, "executing", "done" if succeeded else "failed", result
        )

    def _transition(self, action_id: str, expected: str, new: str, result: str | None) -> Action:
        with closing(self._connect()) as connection, connection:
            changed = connection.execute(
                "UPDATE actions SET status = ?, decided_at = COALESCE(decided_at, ?), result = ? "
                "WHERE id = ? AND status = ?",
                (new, _now(), result, action_id, expected),
            ).rowcount
        action = self.get(action_id)
        if changed != 1:
            raise RuntimeError(
                f"action {action_id} is {action.status}, not {expected}; nothing was changed"
            )
        return action

    @staticmethod
    def _to_action(row: sqlite3.Row) -> Action:
        if _digest(row["payload"]) != row["payload_sha256"]:
            raise ValueError(f"action {row['id']} was altered after it was proposed")
        return Action(
            id=row["id"],
            kind=row["kind"],
            payload=json.loads(row["payload"]),
            payload_sha256=row["payload_sha256"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            decided_at=datetime.fromisoformat(row["decided_at"]) if row["decided_at"] else None,
            result=row["result"],
        )
