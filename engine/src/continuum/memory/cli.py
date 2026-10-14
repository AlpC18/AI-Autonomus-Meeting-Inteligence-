# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Command-line search over stored meeting transcripts."""

import argparse
import os
import sys

from continuum.config import Settings
from continuum.memory.embedder import DEFAULT_MODEL, load_embedder
from continuum.memory.store import MemoryHit, MemoryStore


def search_configured(settings: Settings, query: str, limit: int) -> list[MemoryHit]:
    """Search the memory of the tenant and project named in ``settings``.

    Opens the database only for the duration of the call.

    Raises:
        LookupError: if no tenant and project are configured, or nothing has
            been stored yet.
        RuntimeError: if the database is in use by the running engine.
        ValueError: if ``limit`` is less than 1.
    """
    if settings.scope is None:
        raise LookupError(
            "Set CONTINUUM_TENANT_ID and CONTINUUM_PROJECT_ID to choose whose memory to search."
        )
    if not settings.memory_dir.is_dir():
        raise LookupError(f"No memory has been stored yet at {settings.memory_dir}.")
    model_name = settings.embedding_model or DEFAULT_MODEL
    embed, dimensions = load_embedder(model_name, settings.model_dir)
    with MemoryStore(settings.memory_dir, embed, dimensions, model_name) as store:
        return store.scoped(settings.scope).search(query, limit)


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
    try:
        hits = search_configured(settings, args.query, args.limit)
    except LookupError as error:
        sys.exit(str(error.args[0]))
    except (RuntimeError, ValueError) as error:
        sys.exit(f"Could not search memory (is the engine still running?): {error}")

    if not hits:
        sys.stdout.write("No matching transcript segments.\n")
    for hit in hits:
        sys.stdout.write(
            f"{hit.spoken_at.astimezone():%Y-%m-%d %H:%M:%S}  {hit.speaker}: {hit.text}  (score {hit.score:.2f})\n"
        )
