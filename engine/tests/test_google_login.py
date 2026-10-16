# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""In-app Google consent: loopback redirect, PKCE, state check, token exchange."""

import base64
import hashlib
import threading
import urllib.request
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from continuum.actions.google_login import SCOPES, authorize


def browser(code: str | None = "the-code", state: str | None = None, error: str | None = None):
    """A fake browser: the user consents, and Google redirects to the loopback address."""
    opened: list[str] = []

    def open_url(url: str) -> None:
        opened.append(url)
        query = parse_qs(urlparse(url).query)
        params = {"state": state or query["state"][0]}
        if error:
            params["error"] = error
        elif code:
            params["code"] = code
        redirect = query["redirect_uri"][0] + "/?" + "&".join(f"{k}={v}" for k, v in params.items())
        threading.Thread(target=lambda: urllib.request.urlopen(redirect, timeout=5).read(), daemon=True).start()

    return open_url, opened


def google(exchanged: list[dict[str, list[str]]], reply: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        exchanged.append(parse_qs(request.read().decode()))
        return httpx.Response(200, json=reply)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_consent_returns_the_refresh_token_using_pkce() -> None:
    open_url, opened = browser()
    exchanged: list[dict[str, list[str]]] = []

    token = authorize("id.apps.googleusercontent.com", "secret", open_url, google(exchanged, {"refresh_token": "1//r"}))

    assert token == "1//r"
    query = parse_qs(urlparse(opened[0]).query)
    assert query["scope"][0].split() == list(SCOPES)
    assert query["access_type"] == ["offline"] and query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"][0].startswith("http://127.0.0.1:")
    (sent,) = exchanged
    verifier = sent["code_verifier"][0]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert query["code_challenge"] == [challenge]
    assert sent["code"] == ["the-code"] and sent["redirect_uri"] == query["redirect_uri"]


def test_a_redirect_with_the_wrong_state_is_refused() -> None:
    open_url, _opened = browser(state="forged")
    with pytest.raises(RuntimeError, match="did not match"):
        authorize("id", "secret", open_url, google([], {"refresh_token": "x"}), timeout=5)


def test_declined_consent_and_missing_refresh_token_are_explained() -> None:
    open_url, _opened = browser(error="access_denied")
    with pytest.raises(RuntimeError, match="access_denied"):
        authorize("id", "secret", open_url, google([], {}), timeout=5)
    open_url, _opened = browser()
    with pytest.raises(RuntimeError, match="no refresh token"):
        authorize("id", "secret", open_url, google([], {"access_token": "a"}), timeout=5)
