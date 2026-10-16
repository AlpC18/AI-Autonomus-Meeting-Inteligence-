# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Outside services: rate limits and brief outages are waited out, changes are not repeated blindly."""

import httpx

from continuum.net import RetryTransport


def run(method: str, statuses: list[int], headers: dict[str, str] | None = None) -> tuple[int, int, list[float]]:
    replies = iter(statuses)
    calls = []
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.content)
        return httpx.Response(next(replies), headers=headers or {})

    transport = RetryTransport(httpx.MockTransport(handler), sleep=slept.append)
    with httpx.Client(transport=transport) as client:
        status = client.request(method, "https://api.example.com/x", json={"a": 1}).status_code
    assert all(body == calls[0] for body in calls), "the body must be resent unchanged"
    return status, len(calls), slept


def test_a_rate_limit_is_waited_out_using_retry_after() -> None:
    assert run("POST", [429, 201], {"Retry-After": "3"}) == (201, 2, [3.0])


def test_outages_are_retried_for_reads_with_backoff() -> None:
    assert run("GET", [503, 502, 200]) == (200, 3, [1.0, 2.0])


def test_a_change_is_not_repeated_after_a_server_error() -> None:
    assert run("POST", [503, 201]) == (503, 1, [])


def test_gives_up_after_three_attempts_or_a_long_retry_after() -> None:
    assert run("GET", [429, 429, 429, 200]) == (429, 3, [1.0, 2.0])
    assert run("GET", [429, 200], {"Retry-After": "120"}) == (429, 1, [])


def test_other_errors_are_returned_at_once() -> None:
    assert run("GET", [404]) == (404, 1, [])
