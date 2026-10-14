# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Memory: stored segments are searchable, and never across tenants or projects."""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from continuum.memory.scope import TenantScope
from continuum.memory.store import Meeting, MemoryStore
from continuum.transcript import Segment

DIMENSIONS = 64
STARTED = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
MEETING = Meeting("meeting-1", STARTED)


def embed(texts: list[str]) -> list[np.ndarray]:
    """Deterministic bag-of-words vectors: shared words give similar vectors."""
    vectors = []
    for text in texts:
        vector = np.zeros(DIMENSIONS, dtype=np.float32)
        for word in text.lower().replace(".", "").split():
            vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % DIMENSIONS] += 1.0
        vectors.append(vector / (np.linalg.norm(vector) or 1.0))
    return vectors


def segment(text: str, start: float = 0.0, speaker: str = "others") -> Segment:
    return Segment("system", start, start + 2.0, text, (), speaker)


@pytest.fixture
def store(tmp_path: Path):
    with MemoryStore(tmp_path, embed, DIMENSIONS) as opened:
        yield opened


ACME = TenantScope("acme", "website")
GLOBEX = TenantScope("globex", "website")


def test_stored_segment_is_found_with_its_metadata(store: MemoryStore) -> None:
    memory = store.scoped(ACME)
    memory.add_segment(segment("the budget was revised to 35k", 90.0, "SPEAKER_01"), MEETING)
    memory.add_segment(segment("lunch is at noon"), MEETING)

    hits = memory.search("what is the budget", limit=1)

    assert len(hits) == 1
    hit = hits[0]
    assert hit.text == "the budget was revised to 35k"
    assert hit.speaker == "SPEAKER_01"
    assert hit.meeting_id == "meeting-1"
    assert hit.spoken_at == STARTED + timedelta(seconds=90)
    assert (hit.tenant_id, hit.project_id) == ("acme", "website")


def test_another_tenant_never_sees_the_data(store: MemoryStore) -> None:
    store.scoped(ACME).add_segment(segment("the budget was revised to 35k"), MEETING)

    assert store.scoped(GLOBEX).search("the budget was revised to 35k") == []


def test_another_project_of_the_same_tenant_never_sees_the_data(store: MemoryStore) -> None:
    store.scoped(ACME).add_segment(segment("the budget was revised to 35k"), MEETING)

    assert store.scoped(TenantScope("acme", "mobile")).search("budget") == []


def test_ids_that_concatenate_alike_stay_separate(store: MemoryStore) -> None:
    store.scoped(TenantScope("a", "b-c")).add_segment(segment("secret plan"), MEETING)

    assert store.scoped(TenantScope("a-b", "c")).search("secret plan") == []


def test_each_scope_gets_only_its_own_results(store: MemoryStore) -> None:
    store.scoped(ACME).add_segment(segment("acme budget is 35k"), MEETING)
    store.scoped(GLOBEX).add_segment(segment("globex budget is 90k"), MEETING)

    assert [hit.text for hit in store.scoped(ACME).search("budget")] == ["acme budget is 35k"]
    assert [hit.text for hit in store.scoped(GLOBEX).search("budget")] == ["globex budget is 90k"]


def test_storing_the_same_segment_twice_keeps_one_copy(store: MemoryStore) -> None:
    memory = store.scoped(ACME)
    memory.add_segment(segment("the budget was revised"), MEETING)
    memory.add_segment(segment("the budget was revised"), MEETING)

    assert len(memory.search("budget")) == 1


def test_data_survives_reopening_the_store(tmp_path: Path) -> None:
    with MemoryStore(tmp_path, embed, DIMENSIONS) as first:
        first.scoped(ACME).add_segment(segment("the budget was revised"), MEETING)
    with MemoryStore(tmp_path, embed, DIMENSIONS) as second:
        assert len(second.scoped(ACME).search("budget")) == 1


@pytest.mark.parametrize("bad", ["", " ", "a/b", "../x", "..", ".", "a" * 65, "with space"])
def test_malformed_ids_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        TenantScope(bad, "website")
    with pytest.raises(ValueError):
        TenantScope("acme", bad)


def test_search_limit_must_be_positive(store: MemoryStore) -> None:
    with pytest.raises(ValueError):
        store.scoped(ACME).search("budget", limit=0)


def test_data_stored_with_one_model_is_invisible_to_another(tmp_path: Path) -> None:
    with MemoryStore(tmp_path, embed, DIMENSIONS, "model-a") as first:
        first.scoped(ACME).add_segment(segment("the budget was revised"), MEETING)
    with MemoryStore(tmp_path, embed, DIMENSIONS, "model-b") as second:
        assert second.scoped(ACME).search("budget") == []


def test_old_segments_are_forgotten_only_in_this_scope(store: MemoryStore) -> None:
    acme, globex = store.scoped(ACME), store.scoped(GLOBEX)
    old = Meeting("old", STARTED - timedelta(days=100))
    acme.add_segment(segment("old budget talk"), old)
    acme.add_segment(segment("new budget talk"), MEETING)
    globex.add_segment(segment("globex old budget"), old)

    forgotten = acme.forget_before(STARTED - timedelta(days=30))

    assert forgotten == 1
    assert [hit.text for hit in acme.search("budget talk", limit=5)] == ["new budget talk"]
    assert len(globex.search("budget", limit=5)) == 1
    assert store.scoped(TenantScope("nobody", "none")).forget_before(STARTED) == 0
