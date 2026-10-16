# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Loads the local text-embedding model used by the memory store."""

from pathlib import Path

from fastembed import TextEmbedding

from continuum.memory.store import Embedder

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
"""Small multilingual model, so meetings need not be in English."""


def load_embedder(
    model_name: str = DEFAULT_MODEL, cache_dir: Path | None = None
) -> tuple[Embedder, int]:
    """Load an embedding model and return it with its vector dimension.

    Runs fully on this machine. The model is downloaded on first use into
    ``cache_dir`` (or fastembed's default cache when ``None``), which is slow;
    call this once and from a worker thread.

    Raises:
        ValueError: if ``model_name`` is not a model fastembed supports.
    """
    model = TextEmbedding(model_name, cache_dir=str(cache_dir) if cache_dir else None)

    def embed(texts: list[str]):
        return list(model.embed(texts))

    return embed, len(embed(["dimension probe"])[0])
