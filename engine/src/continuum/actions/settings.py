# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Settings of the action engine, read from environment variables."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ActionSettings:
    """Where actions are queued and what they are allowed to touch.

    ``github_repos`` is the allowlist of ``owner/name`` repositories; empty
    means no GitHub issue may be proposed or created. ``github_token`` is
    needed only to execute an approved action, never to propose one.
    """

    database: Path = Path.home() / ".continuum" / "actions.db"
    github_repos: frozenset[str] = frozenset()
    github_token: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "ActionSettings":
        """Read ``CONTINUUM_ACTIONS_DB``, ``CONTINUUM_GITHUB_REPOS``
        (comma-separated) and ``GITHUB_TOKEN`` from ``env``."""
        database = env.get("CONTINUUM_ACTIONS_DB")
        repos = env.get("CONTINUUM_GITHUB_REPOS", "")
        return cls(
            database=Path(database) if database else cls().database,
            github_repos=frozenset(part.strip() for part in repos.split(",") if part.strip()),
            github_token=env.get("GITHUB_TOKEN") or None,
        )
