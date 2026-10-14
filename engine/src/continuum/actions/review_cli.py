# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Human review of proposed actions: list, approve, or reject them."""

import argparse
import json
import os
import sys

import httpx

from continuum.actions.approval import approve
from continuum.actions.settings import ActionSettings
from continuum.actions.store import Action, ActionStore


def _as_dict(action: Action) -> dict[str, object]:
    return {
        "id": action.id,
        "kind": action.kind,
        "payload": action.payload,
        "status": action.status,
        "created_at": action.created_at.isoformat(),
        "result": action.result,
    }


def _describe(action: Action) -> str:
    lines = [f"Action {action.id} ({action.kind}, {action.status})"]
    for field, value in action.payload.items():
        shown = ", ".join(value) or "none" if isinstance(value, list) else value
        lines.append(f"  {field}: {shown}")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Entry point of ``continuum-actions-review``.

    ``list`` shows what is waiting. ``approve ID`` prints the exact content and
    asks for confirmation before anything is sent; without a terminal to ask
    on it refuses, unless ``--yes`` is given (the desktop app passes it after
    the user clicks Approve). ``reject ID`` discards a proposal. Exit code is
    1 when the action failed or the request was invalid.
    """
    parser = argparse.ArgumentParser(description="Review actions proposed by the assistant.")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="show actions waiting for a decision")
    approve_parser = commands.add_parser("approve", help="execute one pending action")
    approve_parser.add_argument("id")
    approve_parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    reject_parser = commands.add_parser("reject", help="discard one pending action")
    reject_parser.add_argument("id")
    args = parser.parse_args()

    try:
        settings = ActionSettings.from_env(os.environ)
    except ValueError as error:
        sys.exit(str(error))
    store = ActionStore(settings.database)

    def emit(actions: list[Action]) -> None:
        if args.json:
            sys.stdout.write(json.dumps([_as_dict(action) for action in actions]) + "\n")
        elif not actions:
            sys.stdout.write("No actions are waiting for review.\n")
        else:
            sys.stdout.write("\n".join(_describe(action) for action in actions))

    try:
        if args.command == "list":
            emit(store.pending())
            return
        if args.command == "reject":
            emit([store.reject(args.id)])
            return
        action = store.get(args.id)
        if not args.yes:
            if not sys.stdin.isatty():
                sys.exit("Refusing to approve without confirmation: run in a terminal or pass --yes.")
            sys.stdout.write(_describe(action))
            if input("Create this for real? [y/N] ").strip().lower() != "y":
                sys.exit("Not approved; nothing was sent.")
        with httpx.Client(timeout=30) as client:
            done = approve(store, args.id, settings, client)
        emit([done])
        if done.status != "done":
            sys.exit(1)
    except (KeyError, RuntimeError, ValueError) as error:
        sys.exit(str(error.args[0]) if error.args else str(error))
