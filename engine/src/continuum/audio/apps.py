# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Which running apps count as meeting apps, for capturing only their audio."""

from collections.abc import Iterable
from typing import Any

MEETING_APPS = frozenset(
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
        # Browsers, for Google Meet and other calls in a tab. A browser's other
        # tabs are captured too: ScreenCaptureKit separates apps, not tabs.
        "com.google.Chrome",
        "com.apple.Safari",
        "org.mozilla.firefox",
        "com.microsoft.edgemac",
        "com.brave.Browser",
        "company.thebrowser.Browser",
        "com.vivaldi.Vivaldi",
        "com.operasoftware.Opera",
    }
)
"""Bundle IDs of apps whose audio is captured when only meeting apps are heard."""


def meeting_apps(applications: Iterable[Any], allowed: frozenset[str] = MEETING_APPS) -> list[Any]:
    """The ``SCRunningApplication`` objects (anything with ``bundleIdentifier()``) in ``allowed``."""
    return [app for app in applications if app.bundleIdentifier() in allowed]


def bundle_ids(applications: Iterable[Any]) -> frozenset[str]:
    """The bundle IDs of ``applications``, to tell whether the set changed."""
    return frozenset(str(app.bundleIdentifier()) for app in applications)
