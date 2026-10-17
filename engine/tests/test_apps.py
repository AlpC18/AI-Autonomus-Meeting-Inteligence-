# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Choosing the meeting apps whose audio is captured."""

from recall.audio.apps import bundle_ids, meeting_apps


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


def test_teams_slack_and_other_platforms_are_heard() -> None:
    running = [
        App(bundle)
        for bundle in (
            "com.microsoft.teams2", "com.tinyspeck.slackmacgap", "ru.keepcoder.Telegram",
            "com.apple.Safari.WebApp.3F2A0C1E", "com.apple.Safari", "com.spotify.client",
        )
    ]
    assert bundle_ids(meeting_apps(running)) == {
        "com.microsoft.teams2", "com.tinyspeck.slackmacgap", "ru.keepcoder.Telegram",
        "com.apple.Safari.WebApp.3F2A0C1E", "com.apple.Safari",
    }


def test_extra_meeting_apps_come_from_settings() -> None:
    import pytest

    from recall.config import Settings

    settings = Settings.from_env({"RECALL_MEETING_APPS": "com.example.Meet, com.acme.*"})
    assert settings.extra_meeting_apps == {"com.example.Meet", "com.acme.*"}
    assert bundle_ids(meeting_apps([App("com.acme.Call"), App("com.other")], settings.extra_meeting_apps)) == {"com.acme.Call"}
    with pytest.raises(ValueError, match="RECALL_MEETING_APPS"):
        Settings.from_env({"RECALL_MEETING_APPS": "bad id!"})
