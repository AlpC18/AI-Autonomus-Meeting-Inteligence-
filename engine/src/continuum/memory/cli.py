# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Command-line search over stored meeting transcripts."""

import argparse
import os
import sys

from continuum.config import Settings
from continuum.memory.embedder import DEFAULT_MODEL, load_embedder
from continuum.memory.store import MemoryStore


def main() -> None:
    """Search the configured tenant and project (``continuum-memory-search``).

    The scope comes from ``CONTINUUM_TENANT_ID`` and ``CONTINUUM_PROJECT_ID``;
    there is no way to search across scopes. The engine must not be running,
    because only one process can open the memory database at a time.
    """
    parser = argparse.ArgumentParser(description="Search stored meeting transcripts.")
    parser.add_argument("query", help="what to look for, in plain language")
    parser.add_argument("--limit", type=int, default=5, help="maximum results (default 5)")
    args = parser.parse_args()

    try:
        settings = Settings.from_env(os.environ)
    except ValueError as error:
        sys.exit(f"Invalid configuration: {error}")
    if settings.scope is None:
        sys.exit("Set CONTINUUM_TENANT_ID and CONTINUUM_PROJECT_ID to choose whose memory to search.")
    if not settings.memory_dir.is_dir():
        sys.exit(f"No memory has been stored yet at {settings.memory_dir}.")

    model_name = settings.embedding_model or DEFAULT_MODEL
    embed, dimensions = load_embedder(model_name, settings.model_dir)
    try:
        with MemoryStore(settings.memory_dir, embed, dimensions, model_name) as store:
            hits = store.scoped(settings.scope).search(args.query, args.limit)
    except (RuntimeError, ValueError) as error:
        sys.exit(f"Could not search memory (is the engine still running?): {error}")

    if not hits:
        sys.stdout.write("No matching transcript segments.\n")
    for hit in hits:
        sys.stdout.write(
            f"{hit.spoken_at.astimezone():%Y-%m-%d %H:%M:%S}  {hit.speaker}: {hit.text}  (score {hit.score:.2f})\n"
        )
