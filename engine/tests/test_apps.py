# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Choosing the meeting apps whose audio is captured."""

from continuum.audio.apps import bundle_ids, meeting_apps


class App:
    def __init__(self, bundle: str | None) -> None:
        self.bundle = bundle

    def bundleIdentifier(self) -> str | None:
        return self.bundle


def test_only_meeting_apps_are_chosen() -> None:
    running = [App("us.zoom.xos"), App("com.spotify.client"), App(None), App("com.google.Chrome")]
    chosen = meeting_apps(running)
    assert bundle_ids(chosen) == {"us.zoom.xos", "com.google.Chrome"}
    assert meeting_apps(running, frozenset({"com.spotify.client"}))[0].bundle == "com.spotify.client"
