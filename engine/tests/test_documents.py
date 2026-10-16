# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Company documents in memory: split into passages, found by fact checks, replaced on re-import."""

import os
from datetime import UTC, datetime
from pathlib import Path

from test_memory import ACME, DIMENSIONS, embed

from continuum.factcheck.checker import FactChecker
from continuum.memory.documents import (
    document_files,
    forget_document,
    import_document,
    passages,
)
from continuum.memory.store import MemoryStore
from continuum.transcript import Segment

BUDGET = """# Q3 plan

The budget was revised down to $35,000 after the August review.
Launch is planned for March 3rd.

- Hiring: we need 2 engineers.
- Ok.

| Item | Cost |
|------|------|
| Hosting | $1,200 |
"""


def test_documents_are_split_into_sentence_passages() -> None:
    assert passages(BUDGET) == [
        "Q3 plan",
        "The budget was revised down to $35,000 after the August review.",
        "Launch is planned for March 3rd.",
        "Hiring: we need 2 engineers.",
        "Item Cost",
        "Hosting $1,200",
    ]


def test_long_passages_are_cut() -> None:
    (only,) = passages("word " * 400)
    assert len(only) <= 500


def test_folders_yield_supported_files_only(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    for name in ("a.md", "sub/b.txt", "c.png", ".hidden.md"):
        (tmp_path / name).write_text("x")
    assert [path.name for path in document_files([tmp_path])] == ["a.md", "b.txt"]


def test_a_spoken_figure_is_checked_against_a_document(tmp_path: Path) -> None:
    doc = tmp_path / "budget.md"
    doc.write_text(BUDGET)
    os.utime(doc, (1_786_000_000, 1_786_000_000))
    with MemoryStore(tmp_path / "memory", embed, DIMENSIONS) as store:
        memory = store.scoped(ACME)
        assert import_document(memory, doc) == 6

        checker = FactChecker(memory.search, min_score=0.3)
        alert = checker.check(
            Segment("system", 0.0, 2.0, "the budget was revised down to $50,000", (), "Speaker 1")
        )

    assert alert is not None
    assert alert.recorded == ("$35,000",)
    assert alert.record_speaker == "budget.md"
    assert abs(alert.record_spoken_at - datetime.fromtimestamp(1_786_000_000, UTC)).total_seconds() < 1


def test_reimporting_a_shorter_document_drops_old_passages(tmp_path: Path) -> None:
    doc = tmp_path / "budget.md"
    doc.write_text(BUDGET)
    with MemoryStore(tmp_path / "memory", embed, DIMENSIONS) as store:
        memory = store.scoped(ACME)
        import_document(memory, doc)
        doc.write_text("The budget is $40,000.")
        assert import_document(memory, doc) == 1
        assert [hit.text for hit in memory.search("budget", limit=10)] == ["The budget is $40,000."]

        forget_document(memory, doc)
        assert memory.search("budget", limit=10) == []
