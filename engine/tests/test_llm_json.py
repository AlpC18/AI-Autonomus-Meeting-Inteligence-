# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Reading the JSON object out of a model's reply, including small models' slips."""

import pytest

from recall.llm import json_object

# Seen from Qwen2.5-3B: the object is closed after "action_items" and the reply carries on.
CLOSED_EARLY = """{"overview": "Ship 2.1 on Monday.",
 "decisions": ["Ship 2.1 next Monday."],
 "action_items": [{"task": "Review the PR", "owner": "Ana", "due": null}]},
"sections": {"blockers": ["Staging is down."]}}"""


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Sure! Here it is: {"a": {"b": [1, 2]}} Hope that helps.', {"a": {"b": [1, 2]}}),
        ('{"a": 1} and later {"b": 2}', {"a": 1}),
        ('Use {braces} like this: {"a": 1}', {"a": 1}),
    ],
    ids=["bare", "fenced", "prose", "two-objects", "braces-in-prose"],
)
def test_the_object_is_found_however_it_is_wrapped(reply: str, expected: dict) -> None:
    assert json_object(reply) == expected


def test_an_object_closed_too_early_keeps_the_keys_after_it() -> None:
    data = json_object(CLOSED_EARLY)
    assert data is not None
    assert data["overview"] == "Ship 2.1 on Monday."
    assert data["sections"] == {"blockers": ["Staging is down."]}


@pytest.mark.parametrize("reply", ["", "no json here", "[1, 2]", '{"a": ', "{not json}"])
def test_no_object_gives_none(reply: str) -> None:
    assert json_object(reply) is None
