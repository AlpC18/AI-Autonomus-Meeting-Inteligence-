# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Google consent from the desktop app: get a refresh token without copying it by hand.

Uses Google's flow for installed apps: the browser opens Google's consent
page, Google redirects to a one-time listener on ``127.0.0.1``, and the code
is exchanged for tokens with PKCE. The user's own OAuth client (type
"Desktop app") is used, from ``GOOGLE_CLIENT_ID`` and ``GOOGLE_CLIENT_SECRET``.

``continuum-google-login`` prints ``{"refresh_token": ...}`` for the app,
which stores it in the Keychain; nothing is written to disk here.
"""

import base64
import hashlib
import json
import os
import secrets
import sys
import time
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from continuum import net

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = (
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
)
TIMEOUT_S = 300.0

_PAGE = (
    b"<!doctype html><meta charset=utf-8><title>Continuum</title>"
    b"<p style='font:16px system-ui;margin:3em'>%s You can close this tab.</p>"
)


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class _Redirect(BaseHTTPRequestHandler):
    """Receives Google's redirect once and stores its query on the server."""

    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        if "code" not in query and "error" not in query:
            self.send_response(404)
            self.end_headers()
            return
        self.server.query = {key: values[0] for key, values in query.items()}  # type: ignore[attr-defined]
        ok = "code" in query
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_PAGE % (b"Continuum received the answer from Google." if ok else b"Google was not connected."))

    def log_message(self, format: str, *args: object) -> None:
        """Silence: the query holds the authorization code."""


def _wait_for_redirect(server: HTTPServer, timeout: float) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    server.query = None  # type: ignore[attr-defined]
    while server.query is None:  # type: ignore[attr-defined]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Google consent timed out; try again.")
        server.timeout = min(remaining, 1.0)
        server.handle_request()
    return server.query  # type: ignore[attr-defined,no-any-return]


def authorize(
    client_id: str,
    client_secret: str,
    open_url: Callable[[str], object],
    client: httpx.Client,
    timeout: float = TIMEOUT_S,
) -> str:
    """Ask the user for consent and return the refresh token. Blocks until done.

    Raises:
        RuntimeError: if consent is declined or times out, the redirect does
            not carry this request's state, or Google returns no refresh token.
    """
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(24)
    with HTTPServer(("127.0.0.1", 0), _Redirect) as server:
        redirect_uri = f"http://127.0.0.1:{server.server_address[1]}"
        open_url(
            AUTH_URL
            + "?"
            + urlencode(
                {
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "scope": " ".join(SCOPES),
                    "access_type": "offline",
                    "prompt": "consent",
                    "state": state,
                    "code_challenge": _challenge(verifier),
                    "code_challenge_method": "S256",
                }
            )
        )
        query = _wait_for_redirect(server, timeout)
    if not secrets.compare_digest(query.get("state", ""), state):
        raise RuntimeError("The answer from Google did not match this request; try again.")
    if "error" in query:
        raise RuntimeError(f"Google consent was not given ({query['error'][:60]}).")
    try:
        response = client.post(
            TOKEN_URL,
            data={
                "code": query["code"],
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
    except httpx.HTTPError as error:
        raise RuntimeError(f"Google could not be reached ({type(error).__name__})") from None
    if response.status_code != 200:
        raise RuntimeError(f"Google refused the sign-in (HTTP {response.status_code}).")
    token = response.json().get("refresh_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Google returned no refresh token; remove the app's access in your Google account and retry.")
    return token


def main() -> None:
    """Console entry point (``continuum-google-login``): prints JSON for the desktop app."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print(json.dumps({"error": "Set the Google client ID and secret first (a 'Desktop app' OAuth client)."}))
        sys.exit(1)
    try:
        with net.client(20) as client:
            token = authorize(client_id, client_secret, webbrowser.open, client)
    except RuntimeError as error:
        print(json.dumps({"error": str(error)}))
        sys.exit(1)
    print(json.dumps({"refresh_token": token}))
