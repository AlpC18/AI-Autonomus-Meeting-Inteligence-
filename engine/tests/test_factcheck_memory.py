# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Fact checking against the real store: alerts use only the caller's own scope."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from continuum.factcheck.checker import FactChecker
from continuum.memory.scope import TenantScope
from continuum.memory.store import Meeting, MemoryStore
from continuum.transcript import Segment

DIMENSIONS = 64
MEETING = Meeting("meeting-1", datetime(2026, 8, 14, 10, 0, tzinfo=UTC))


def embed(texts: list[str]) -> list[np.ndarray]:
    vectors = []
    for text in texts:
        vector = np.zeros(DIMENSIONS, dtype=np.float32)
        for word in text.lower().replace(".", "").split():
            vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % DIMENSIONS] += 1.0
        vectors.append(vector / (np.linalg.norm(vector) or 1.0))
    return vectors


def said(text: str) -> Segment:
    return Segment("system", 0.0, 2.0, text, (), "others")


def test_contradiction_is_found_in_own_scope_and_not_in_another(tmp_path: Path) -> None:
    with MemoryStore(tmp_path, embed, DIMENSIONS) as store:
        acme = store.scoped(TenantScope("acme", "website"))
        globex = store.scoped(TenantScope("globex", "website"))
        acme.add_segment(said("the budget was revised to $35,000"), MEETING)

        own = FactChecker(acme.search).check(said("the budget was $50k"))
        other = FactChecker(globex.search).check(said("the budget was $50k"))

    assert own is not None and own.recorded == ("$35,000",)
    assert other is None


def test_a_flagged_claim_does_not_become_the_record(tmp_path: Path) -> None:
    with MemoryStore(tmp_path, embed, DIMENSIONS) as store:
        memory = store.scoped(TenantScope("acme", "website"))
        checker = FactChecker(memory.search)
        memory.add_segment(said("the budget was revised to $35,000"), MEETING)

        wrong = Segment("system", 10.0, 12.0, "the budget was $50k", (), "others")
        assert checker.check(wrong) is not None
        memory.add_segment(wrong, MEETING, disputed=True)

        repeated = Segment("system", 20.0, 22.0, "the budget was $50k", (), "others")
        correct = Segment("system", 30.0, 32.0, "the budget was $35k", (), "others")
        assert checker.check(repeated) is not None
        assert checker.check(correct) is None
