# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Which running apps count as meeting apps, for capturing only their audio."""

from collections.abc import Iterable
from typing import Any

NATIVE_MEETING_APPS = frozenset(
    {
        "us.zoom.xos",
        "com.microsoft.teams",
        "com.microsoft.teams2",
        "com.cisco.webexmeetingsapp",
        "Cisco-Systems.Spark",
        "com.apple.FaceTime",
        "com.tinyspeck.slackmacgap",
        "com.hnc.Discord",
        "net.whatsapp.WhatsApp",
        "com.skype.skype",
        "com.around.Around",
        "com.microsoft.SkypeForBusiness",
        "ru.keepcoder.Telegram",
        "com.tdesktop.Telegram",
        "com.viber.osx",
        "org.whispersystems.signal-desktop",
        "com.tencent.xinWeChat",
        "jp.naver.line.mac",
        "com.amazon.Amazon-Chime",
        "com.logmein.GoToMeeting",
        "com.ringcentral.glip",
        "org.jitsi.jitsi-meet",
        "im.riot.app",
        "app.tuple.app",
    }
)
"""Bundle IDs of meeting apps other than browsers. Others can be added with
``CONTINUUM_MEETING_APPS``."""

BROWSERS = frozenset(
    {
        "com.google.Chrome",
        "com.apple.Safari",
        "org.mozilla.firefox",
        "com.microsoft.edgemac",
        "com.brave.Browser",
        "company.thebrowser.Browser",
        "com.vivaldi.Vivaldi",
        "com.operasoftware.Opera",
        # Sites added to the Dock from Safari ("Add to Dock"), such as Meet.
        "com.apple.Safari.WebApp.*",
    }
)
"""Browsers, for Google Meet and other calls in a tab. ScreenCaptureKit separates
apps, not tabs, so all of a browser's tabs are heard; the browser extension
(``CONTINUUM_BROWSER_TAB_AUDIO``) captures only the meeting tab instead."""

MEETING_APPS = NATIVE_MEETING_APPS | BROWSERS
"""Bundle IDs of apps whose audio is captured when only meeting apps are heard."""


def allows(allowed: frozenset[str], bundle_id: str) -> bool:
    """Whether ``bundle_id`` is in ``allowed``, where an entry ending in ``*`` is a prefix."""
    return bundle_id in allowed or any(
        entry.endswith("*") and bundle_id.startswith(entry[:-1]) for entry in allowed
    )


def meeting_apps(applications: Iterable[Any], allowed: frozenset[str] = MEETING_APPS) -> list[Any]:
    """The ``SCRunningApplication`` objects (anything with ``bundleIdentifier()``) in ``allowed``."""
    return [app for app in applications if allows(allowed, str(app.bundleIdentifier() or ""))]


def bundle_ids(applications: Iterable[Any]) -> frozenset[str]:
    """The bundle IDs of ``applications``, to tell whether the set changed."""
    return frozenset(str(app.bundleIdentifier()) for app in applications)
