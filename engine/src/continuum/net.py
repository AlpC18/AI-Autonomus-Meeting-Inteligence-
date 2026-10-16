# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""HTTP clients for outside services that wait out rate limits and brief outages.

GitHub, Jira, Slack and the AI providers answer 429 when called too often
and 502-504 while restarting. A request is retried a few times, honouring
``Retry-After``. Only 429 is retried for requests that change something
(POST and the like): it means the request was not processed, whereas a 5xx
may come after the change was made.
"""

import time
from collections.abc import Callable

import httpx

ATTEMPTS = 3
MAX_WAIT_S = 10.0
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_BUSY = frozenset({429})
_DOWN = frozenset({502, 503, 504})


def _wait(response: httpx.Response, attempt: int) -> float:
    """Seconds to wait before the next attempt: ``Retry-After`` if given, else 1, 2, 4..."""
    try:
        return max(0.0, float(response.headers["Retry-After"]))
    except (KeyError, ValueError):
        return float(2**attempt)


class RetryTransport(httpx.BaseTransport):
    """Wraps ``inner`` and repeats rate-limited or failed-over requests."""

    def __init__(
        self,
        inner: httpx.BaseTransport | None = None,
        attempts: int = ATTEMPTS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._inner = inner or httpx.HTTPTransport(retries=1)
        self._attempts = attempts
        self._sleep = sleep

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        retry_on = _BUSY | _DOWN if request.method in _SAFE_METHODS else _BUSY
        for attempt in range(self._attempts):
            response = self._inner.handle_request(request)
            wait = _wait(response, attempt)
            if response.status_code not in retry_on or attempt == self._attempts - 1 or wait > MAX_WAIT_S:
                return response
            response.close()
            self._sleep(wait)
        raise AssertionError("unreachable")

    def close(self) -> None:
        self._inner.close()


def client(timeout: float) -> httpx.Client:
    """An ``httpx.Client`` with :class:`RetryTransport`."""
    return httpx.Client(timeout=timeout, transport=RetryTransport())
