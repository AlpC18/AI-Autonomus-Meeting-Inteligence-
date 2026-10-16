# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Shared slides: only meeting windows are read, and each new line with a figure is checked once."""

import asyncio
from types import SimpleNamespace

from continuum.screen import NewLines, meeting_windows, watch_slides
from continuum.transcript import Segment


def window(bundle: str, title: str, width: float = 1200, height: float = 800, on_screen: bool = True):
    app = SimpleNamespace(bundleIdentifier=lambda: bundle)
    frame = SimpleNamespace(size=SimpleNamespace(width=width, height=height))
    return SimpleNamespace(owningApplication=lambda: app, title=lambda: title, frame=lambda: frame, isOnScreen=lambda: on_screen)


def test_only_meeting_windows_are_read() -> None:
    windows = [
        window("us.zoom.xos", "Zoom Meeting"),
        window("com.google.Chrome", "Google Meet - Budget review"),
        window("com.google.Chrome", "Inbox (1,609) - Gmail"),  # never the user's mail
        window("com.apple.Safari.WebApp.1D69", "Microsoft Teams"),
        window("com.apple.mail", "Meet me tomorrow"),  # not a meeting app
        window("us.zoom.xos", "Zoom", width=200, height=60),  # a toolbar
        window("us.zoom.xos", "Zoom Meeting", on_screen=False),
    ]
    assert [w.title() for w in meeting_windows(windows)] == ["Zoom Meeting", "Google Meet - Budget review", "Microsoft Teams"]


def test_each_new_line_with_a_figure_is_returned_once() -> None:
    new_lines = NewLines()
    slide = ["Q3 plan", "Revenue grew 12% in Q3", "Budget: $59,000 per year", "Page 3"]
    assert new_lines(slide) == ["Revenue grew 12% in Q3", "Budget: $59,000 per year"]
    assert new_lines(slide + ["Hiring 4 engineers next quarter"]) == ["Hiring 4 engineers next quarter"]


async def test_new_slide_lines_are_fact_checked_as_the_shared_screen() -> None:
    checked: list[Segment] = []
    reads = iter([["Budget: $59,000 per year"], ["Budget: $59,000 per year"], PermissionError("denied")])

    async def read() -> list[str]:
        result = next(reads)
        if isinstance(result, Exception):
            raise result
        return result

    async def check(segment: Segment) -> None:
        checked.append(segment)

    await asyncio.wait_for(watch_slides(check, read, scan_s=0), 2)
    assert [(s.source, s.speaker, s.text) for s in checked] == [("screen", "Shared screen", "Budget: $59,000 per year")]
