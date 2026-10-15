# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Summarises meeting notes with the configured language model.

Action items can be turned into proposals (calendar deadlines, Jira or
GitHub issues, a Slack recap). Those are only queued: each one still waits
for a person to approve it in the desktop app or ``continuum-actions-review``.
"""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date
from pathlib import Path

from continuum.actions import proposals
from continuum.actions.settings import ActionSettings
from continuum.actions.store import ActionStore
from continuum.llm import LlmSettings, connect
from continuum.summary import MeetingSummary, summarize, to_markdown

SUMMARY_HEADING = "\n## Summary\n"
_SLACK_LIMIT = 3000


def split_summary(notes: str) -> str:
    """Return ``notes`` without a summary section written earlier by this tool."""
    return notes.split(SUMMARY_HEADING, 1)[0].rstrip() + "\n"


def _slack_text(summary: MeetingSummary, title: str) -> str:
    lines = [f"*{title}*", summary.overview]
    lines += [f"• {item.task}" + (f" ({item.owner})" if item.owner else "") for item in summary.action_items]
    text = "\n".join(lines)
    return text if len(text) <= _SLACK_LIMIT else text[: _SLACK_LIMIT - 1] + "…"


def build_proposals(
    summary: MeetingSummary,
    targets: list[str],
    settings: ActionSettings,
    source: str,
    attendees: Sequence[str] = (),
    title: str = "",
) -> tuple[list[proposals.Proposal], list[str]]:
    """Turn the summary into proposals for each target; return them and any errors.

    Targets: ``calendar`` (items with a due date), ``slack`` (one recap),
    ``email`` (one recap to the calendar event's ``attendees``),
    ``jira:KEY`` and ``github:owner/name`` (one issue per action item). An
    item that a target refuses is reported, not fatal.
    """
    built: list[proposals.Proposal] = []
    errors: list[str] = []

    def attempt(label: str, make) -> None:
        try:
            built.append(make())
        except (ValueError, PermissionError) as error:
            errors.append(f"{label}: {error}")

    for target in targets:
        kind, _, where = target.partition(":")
        if kind == "slack":
            attempt("slack", lambda: proposals.slack_message(settings, _slack_text(summary, source)))
            continue
        if kind == "email":
            subject = f"Recap: {title or 'our meeting'}"[:200]
            attempt(
                "email",
                lambda subject=subject: proposals.email_recap(
                    settings, attendees, subject, to_markdown(summary)
                ),
            )
            continue
        for item in summary.action_items:
            details = "\n".join(
                part
                for part in (
                    f"Owner: {item.owner}" if item.owner else "",
                    f"Due: {item.due}" if item.due else "",
                    f"From the meeting notes {source}.",
                )
                if part
            )
            if kind == "calendar" and item.due:
                attempt(
                    f"calendar ({item.task})",
                    lambda item=item, details=details: proposals.calendar_deadline(
                        settings, item.task, item.due, details
                    ),
                )
            elif kind == "jira":
                attempt(
                    f"jira ({item.task})",
                    lambda item=item, details=details, where=where: proposals.jira_issue(
                        settings, where, item.task, details
                    ),
                )
            elif kind == "github":
                attempt(
                    f"github ({item.task})",
                    lambda item=item, details=details, where=where: proposals.github_issue(
                        settings, where, item.task, details
                    ),
                )
    return built, errors


def _target(value: str) -> str:
    kind, _, where = value.partition(":")
    if (kind in {"calendar", "slack", "email"} and not where) or (kind in {"jira", "github"} and where):
        return value
    raise argparse.ArgumentTypeError(
        "use calendar, slack, jira:PROJECT or github:owner/name"
    )


def main() -> None:
    """Entry point of ``continuum-summarize``.

    Reads Markdown notes (as written by the engine or ``continuum-transcribe``)
    or a plain-text transcript and prints a summary with decisions and action
    items. ``--write`` adds it to the notes file (replacing an earlier one);
    ``--propose`` queues proposals for approval. The model is chosen with
    ``CONTINUUM_LLM_PROVIDER``; the transcript is sent to that provider.
    """
    parser = argparse.ArgumentParser(description="Summarise meeting notes with an AI model.")
    parser.add_argument("notes", type=Path, help="Markdown notes or a text transcript")
    parser.add_argument("--write", action="store_true", help="add the summary to the notes file")
    parser.add_argument(
        "--propose",
        action="append",
        default=[],
        type=_target,
        metavar="TARGET",
        help="queue proposals: calendar, slack, jira:PROJECT, github:owner/name (repeatable)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not args.notes.is_file():
        sys.exit(f"No such file: {args.notes}")
    try:
        llm_settings = LlmSettings.from_env(os.environ)
        action_settings = ActionSettings.from_env(os.environ) if args.propose else None
    except ValueError as error:
        sys.exit(f"Invalid configuration: {error}")
    if llm_settings is None:
        sys.exit(
            "No AI model is configured. Set CONTINUUM_LLM_PROVIDER (for example groq, gemini, "
            "ollama or anthropic) and its API key; see engine/.env.example."
        )

    notes = args.notes.read_text(encoding="utf-8")
    try:
        summary = summarize(split_summary(notes), connect(llm_settings), today=date.today())
    except (ValueError, RuntimeError) as error:
        sys.exit(str(error))

    queued: list[str] = []
    errors: list[str] = []
    if action_settings is not None:
        built, errors = build_proposals(summary, args.propose, action_settings, args.notes.name)
        store = ActionStore(action_settings.database)
        for proposal in built:
            try:
                queued.append(proposals.queue(store, proposal).id)
            except RuntimeError as error:
                errors.append(str(error))

    if args.write:
        args.notes.write_text(split_summary(notes) + "\n" + to_markdown(summary), encoding="utf-8")
    if args.json:
        sys.stdout.write(
            json.dumps({**asdict(summary), "queued": queued, "errors": errors}, ensure_ascii=False)
            + "\n"
        )
    else:
        sys.stdout.write(to_markdown(summary))
        if queued:
            sys.stdout.write(
                f"\n{len(queued)} proposal(s) queued. Nothing has been sent: approve them in the "
                "desktop app or with continuum-actions-review.\n"
            )
        for error in errors:
            sys.stderr.write(f"Not proposed: {error}\n")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
