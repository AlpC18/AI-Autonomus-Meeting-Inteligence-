# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Checks the whole configuration at once, for the desktop app's settings screen."""

import json
import os
import sys
from collections.abc import Mapping

from recall.actions.settings import ActionSettings
from recall.config import Settings
from recall.llm import LlmSettings


def problems(env: Mapping[str, str]) -> list[str]:
    """Every configuration problem in ``env``, each a sentence for the user."""
    found = []
    for read in (Settings.from_env, ActionSettings.from_env, LlmSettings.from_env):
        try:
            read(env)
        except ValueError as error:
            found.append(str(error))
    try:
        settings = Settings.from_env(env)
    except ValueError:
        return found
    if settings.notes_dir is not None and settings.notes_dir.exists() and not os.access(settings.notes_dir, os.W_OK):
        found.append(f"The notes folder {settings.notes_dir} cannot be written to.")
    return found


def main() -> None:
    """Entry point of ``recall-check-config``: prints ``{"problems": [...]}``; exit 1 if any."""
    found = problems(os.environ)
    sys.stdout.write(json.dumps({"problems": found}) + "\n")
    if found:
        sys.exit(1)


if __name__ == "__main__":
    main()
