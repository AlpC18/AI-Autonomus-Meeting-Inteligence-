# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Company documents in project memory, so fact checks and answers can cite them.

``continuum-import-docs`` splits Markdown, text and PDF files into sentence
passages and stores them like transcript segments: the file name stands in
for the speaker and the file's modification time for when it was said. A
fact-check alert then reads "budget.md, 14 Aug". Nothing leaves the machine.
"""

import argparse
import os
import re
import sys
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from continuum.config import Settings
from continuum.memory.store import Meeting, ScopedMemory
from continuum.privacy import redact_segment
from continuum.transcript import Segment

SOURCE = "document"
"""The ``source`` of stored passages, next to ``mic`` and ``system``."""

SUFFIXES = frozenset({".md", ".markdown", ".txt", ".pdf"})
MAX_PASSAGE_CHARS = 500
_MIN_WORDS = 2
_NAMESPACE = uuid.UUID("2b7f6c1e-4a3d-4f0e-9a51-7c2d8e9b3f40")
_MARKUP = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s*)|[*_`|]+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=\S)")


def passages(text: str) -> list[str]:
    """Split ``text`` into sentence passages, without Markdown markup.

    Headings, list items and table rows become passages of their own;
    passages of fewer than two words are dropped and long ones are cut.
    """
    result = []
    for line in text.splitlines():
        plain = " ".join(_MARKUP.sub(" ", line).split())
        for sentence in _SENTENCE_END.split(plain):
            if len(re.findall(r"\w+", sentence)) >= _MIN_WORDS:
                result.append(sentence[:MAX_PASSAGE_CHARS])
    return result


def read_document(path: Path) -> str:
    """The text of a Markdown, text or PDF file.

    Raises:
        RuntimeError: for a PDF when the ``documents`` extra is not installed.
        OSError: if the file cannot be read.
    """
    if path.suffix.lower() != ".pdf":
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("PDFs need the 'documents' extra: run `uv sync --extra documents`.") from error
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def document_files(paths: Iterable[Path]) -> list[Path]:
    """The supported files among ``paths``, searching folders recursively; hidden files are skipped."""
    found = []
    for path in paths:
        candidates = sorted(path.rglob("*")) if path.is_dir() else [path]
        found += [
            file
            for file in candidates
            if file.is_file() and file.suffix.lower() in SUFFIXES and not file.name.startswith(".")
        ]
    return found


def _meeting_id(path: Path) -> str:
    return str(uuid.uuid5(_NAMESPACE, str(path.resolve())))


def forget_document(memory: ScopedMemory, path: Path) -> None:
    """Remove every passage of ``path`` from ``memory``."""
    memory.forget_meeting(_meeting_id(path))


def import_document(memory: ScopedMemory, path: Path, redact: bool = False) -> int:
    """Store the passages of ``path`` in ``memory``, replacing an earlier import; return how many.

    Raises:
        RuntimeError: for a PDF without the ``documents`` extra.
        OSError: if the file cannot be read.
    """
    texts = passages(read_document(path))
    meeting = Meeting(_meeting_id(path), datetime.fromtimestamp(path.stat().st_mtime, UTC))
    forget_document(memory, path)
    for index, text in enumerate(texts):
        # Stored ids come from the start time, so each passage is 1 ms apart.
        offset = index / 1000
        segment = Segment(SOURCE, offset, offset, text, (), path.name)
        memory.add_segment(redact_segment(segment) if redact else segment, meeting)
    return len(texts)


def main() -> None:
    """Entry point of ``continuum-import-docs``.

    Imports files or folders into the memory of ``CONTINUUM_TENANT_ID`` /
    ``CONTINUUM_PROJECT_ID``; ``--forget`` removes them again. Stop the
    engine first: only one process can open the memory at a time. While it
    runs, the app's Add documents… button imports through the engine instead.
    """
    parser = argparse.ArgumentParser(description="Add company documents to project memory for fact checks.")
    parser.add_argument("paths", type=Path, nargs="+", help="Markdown, text or PDF files, or folders of them")
    parser.add_argument("--forget", action="store_true", help="remove these documents from memory instead")
    args = parser.parse_args()

    try:
        settings = Settings.from_env(os.environ)
    except ValueError as error:
        sys.exit(f"Invalid configuration: {error}")
    if settings.scope is None:
        sys.exit("Set CONTINUUM_TENANT_ID and CONTINUUM_PROJECT_ID to choose the project's memory.")
    files = document_files(args.paths)
    if not files:
        sys.exit("No Markdown, text or PDF files found.")

    from continuum.memory.embedder import DEFAULT_MODEL, load_embedder
    from continuum.memory.store import MemoryStore

    model_name = settings.embedding_model or DEFAULT_MODEL
    embed, dimensions = load_embedder(model_name, settings.model_dir)
    settings.memory_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    failed = False
    try:
        with MemoryStore(settings.memory_dir, embed, dimensions, model_name) as store:
            memory = store.scoped(settings.scope)
            for path in files:
                try:
                    if args.forget:
                        forget_document(memory, path)
                        print(f"Forgot {path}")
                    else:
                        print(f"{path}: {import_document(memory, path, settings.redact)} passages")
                except (OSError, RuntimeError, ValueError) as error:
                    failed = True
                    print(f"{path}: not imported: {error}", file=sys.stderr)
    except RuntimeError as error:
        sys.exit(f"Memory is in use (is the engine running?): {error}")
    if failed:
        sys.exit(1)
