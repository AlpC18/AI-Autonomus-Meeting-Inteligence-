# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""AI fact checking: only close records, bounded calls, untrusted replies."""

import json
from datetime import UTC, datetime

from recall.factcheck.semantic import SemanticChecker
from recall.memory.store import MemoryHit
from recall.transcript import Segment

RECORD = MemoryHit("We chose Paddle as the payment provider", "Ana", "system", "m1",
                   datetime(2026, 9, 1, tzinfo=UTC), 0.7, "acme", "web")
SAID = Segment("system", 0, 3, "As agreed we are going with Stripe for payments", (), "Mark")


class FakeLlm:
    def __init__(self, reply: str) -> None:
        self.reply, self.calls = reply, 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        assert "never instructions" in system and "<statement>Mark:" in user
        return self.reply


def checker(llm, hits=(RECORD,), clock=None):
    times = iter(clock or [0.0, 100.0, 200.0])
    return SemanticChecker(lambda text, limit: list(hits), llm, clock=lambda: next(times))


def test_contradiction_becomes_an_alert_with_explanation() -> None:
    llm = FakeLlm(json.dumps({"contradicts": True, "record": 1, "explanation": "Paddle was chosen, not Stripe."}))
    alert = checker(llm).check(SAID)
    assert alert is not None and alert.claimed == () and alert.record_text == RECORD.text
    assert alert.explanation == "Paddle was chosen, not Stripe."
    assert alert.to_dict()["explanation"]


def test_no_alert_when_the_model_disagrees_or_answers_badly() -> None:
    for reply in ('{"contradicts": false}', '{"contradicts": true, "record": 7}', "nonsense", '{"contradicts": "yes", "record": 1}'):
        assert checker(FakeLlm(reply)).check(SAID) is None


def test_short_statements_weak_matches_and_disputed_records_are_not_sent() -> None:
    llm = FakeLlm('{"contradicts": true, "record": 1}')
    assert checker(llm).check(Segment("system", 0, 1, "Stripe it is", (), "Mark")) is None
    from dataclasses import replace
    assert checker(llm, hits=[replace(RECORD, score=0.2)]).check(SAID) is None
    assert checker(llm, hits=[replace(RECORD, disputed=True)]).check(SAID) is None
    assert llm.calls == 0


def test_cooldown_limits_model_calls() -> None:
    llm = FakeLlm('{"contradicts": false}')
    limited = checker(llm, clock=[0.0, 5.0, 25.0])
    for _ in range(3):
        limited.check(SAID)
    assert llm.calls == 2
