# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""A diagnostics report to attach to a bug report, safe to share.

``continuum-diagnostics`` prints versions, the platform, the non-secret
settings, which secrets are set (never their values), configuration
problems and the end of the engine log. Secret values, e-mail addresses,
phone and card numbers are removed from the log first.
"""

import logging
import logging.handlers
import os
import platform
import sys
from collections.abc import Mapping
from importlib import metadata
from pathlib import Path

from continuum.config_check import problems
from continuum.privacy import redact

LOG_FILE = Path.home() / ".continuum" / "logs" / "engine.log"
LOG_BYTES = 1_000_000
LOG_LINES = 200
_SECRET_WORDS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "WEBHOOK")
_SHOWN_PREFIXES = ("CONTINUUM_", "GOOGLE_CLIENT_ID", "JIRA_EMAIL")
_OWN_SECRETS = frozenset(
    {
        "GITHUB_TOKEN", "GITLAB_TOKEN", "JIRA_API_TOKEN", "NOTION_TOKEN", "HF_TOKEN",
        "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN",
    }
)


def log_to_file(path: Path = LOG_FILE) -> None:
    """Also write the engine's log to ``path`` (1 MB, two old files kept), private to the user."""
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=LOG_BYTES, backupCount=2, encoding="utf-8")
    except OSError as error:
        logging.getLogger(__name__).warning("Not keeping a log file: %s", error)
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(handler)
    if os.name == "posix":
        path.chmod(0o600)


def is_secret(name: str) -> bool:
    return any(word in name.upper() for word in _SECRET_WORDS)


def _tail(path: Path, lines: int) -> list[str]:
    try:
        with path.open(encoding="utf-8", errors="replace") as log:
            return log.read().splitlines()[-lines:]
    except OSError:
        return []


def report(env: Mapping[str, str], log: Path = LOG_FILE, lines: int = LOG_LINES) -> str:
    """The diagnostics report as Markdown."""
    # Every secret-looking value is scrubbed from the log; only Continuum's own are listed.
    scrubbed = [name for name in env if is_secret(name) and env[name]]
    secrets = sorted(
        name for name in scrubbed
        if name in _OWN_SECRETS or name.endswith("_API_KEY") or name.startswith("CONTINUUM_")
    )
    shown = sorted(
        (name, value) for name, value in env.items() if name.startswith(_SHOWN_PREFIXES) and not is_secret(name)
    )
    values = sorted((value for name in scrubbed if len(value := env[name]) >= 4), key=len, reverse=True)

    def clean(text: str) -> str:
        for value in values:
            text = text.replace(value, "[secret]")
        return redact(text)

    try:
        version = metadata.version("continuum")
    except metadata.PackageNotFoundError:
        version = "unknown"
    found = problems(env)
    parts = [
        "# Continuum diagnostics",
        "",
        f"- Continuum engine {version}, Python {platform.python_version()}",
        f"- {platform.platform()} ({platform.machine()})",
        "",
        "## Settings",
        "",
        *(f"- `{name}` = `{clean(value)}`" for name, value in shown),
        *(f"- `{name}` is set" for name in secrets),
        "",
        "## Configuration problems",
        "",
        *([f"- {clean(problem)}" for problem in found] or ["- none"]),
        "",
        f"## Engine log (last {lines} lines)",
        "",
        "```",
        *(clean(line) for line in _tail(log, lines)),
        "```",
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    """Entry point of ``continuum-diagnostics``: prints the report."""
    sys.stdout.write(report(os.environ))


if __name__ == "__main__":
    main()
