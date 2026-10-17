# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Fact checking: a figure that differs from the latest record raises an alert."""

from datetime import UTC, datetime

from recall.factcheck.checker import FactChecker
from recall.memory.store import MemoryHit
from recall.transcript import Segment

AUGUST = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
JUNE = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)


def hit(text: str, spoken_at: datetime = AUGUST, score: float = 0.8) -> MemoryHit:
    return MemoryHit(text, "SPEAKER_01", "system", "meeting-1", spoken_at, score, "acme", "web")


def statement(text: str) -> Segment:
    return Segment("system", 0.0, 2.0, text, (), "others")


def checker(*hits: MemoryHit) -> FactChecker:
    return FactChecker(lambda _query, _limit: list(hits))


def test_different_amount_than_the_record_raises_an_alert() -> None:
    alert = checker(hit("the budget was revised down to $35,000")).check(
        statement("the budget was $50k")
    )

    assert alert is not None
    assert alert.claimed == ("$50k",)
    assert alert.recorded == ("$35,000",)
    assert alert.record_text == "the budget was revised down to $35,000"
    assert alert.record_spoken_at == AUGUST
    assert alert.speaker == "others"


def test_same_amount_in_other_words_is_not_flagged() -> None:
    assert (
        checker(hit("the budget was revised down to $35,000")).check(
            statement("so the budget is 35 thousand dollars")
        )
        is None
    )


def test_the_most_recent_record_wins_over_older_ones() -> None:
    old = hit("the budget is $50,000", JUNE, score=0.9)
    new = hit("the budget was revised down to $35,000", AUGUST, score=0.7)

    assert checker(old, new).check(statement("the budget is $35k")) is None
    alert = checker(old, new).check(statement("the budget is $50k"))
    assert alert is not None and alert.recorded == ("$35,000",)


def test_statement_without_figures_is_never_searched() -> None:
    def search(_query: str, _limit: int) -> list[MemoryHit]:
        raise AssertionError("memory must not be searched")

    assert FactChecker(search).check(statement("let us move on")) is None


def test_weakly_related_record_is_ignored() -> None:
    weak = hit("lunch cost $12", score=0.2)

    assert checker(weak).check(statement("the budget was $50k")) is None


def test_figures_of_different_kinds_are_not_compared() -> None:
    assert checker(hit("the deadline is in 3 weeks")).check(statement("the budget was $50k")) is None


def test_only_the_conflicting_kind_is_reported() -> None:
    alert = checker(hit("$35,000 over 6 months")).check(statement("$35k over 9 months"))

    assert alert is not None
    assert alert.claimed == ("9 months",)
    assert alert.recorded == ("6 months",)


def test_alert_serialises_to_json_types() -> None:
    alert = checker(hit("the budget is $35,000")).check(statement("the budget is $50k"))

    assert alert is not None
    data = alert.to_dict()
    assert data["record_spoken_at"] == "2026-08-14T10:00:00+00:00"
    assert data["claimed"] == ("$50k",)


def test_memory_is_searched_by_topic_without_the_figures() -> None:
    queries = []

    def search(query: str, _limit: int) -> list[MemoryHit]:
        queries.append(query)
        return []

    FactChecker(search).check(statement("the budget was $50k for 6 months"))

    assert queries == ["the budget was for"]
