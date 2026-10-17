# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Fact-checks the figures on shared slides, read from the meeting window (macOS).

Every few seconds the meeting's window is captured and its text read with
macOS's on-device text recognition (Vision); nothing leaves the machine.
Only meeting windows are read: those of native meeting apps, and browser
windows whose title names a meeting site (a browser window can show
anything, such as the user's mail). New lines with a figure in them are
checked against memory like speech, and remembered as said by "Shared screen".
"""

import asyncio
import logging
import re
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from recall.audio.apps import BROWSERS, NATIVE_MEETING_APPS, allows
from recall.factcheck.figures import extract_figures
from recall.transcript import Segment

logger = logging.getLogger(__name__)

SOURCE = "screen"
SPEAKER = "Shared screen"
SCAN_S = 10.0
MIN_WIDTH, MIN_HEIGHT = 400, 300
"""Smaller windows are toolbars and pop-ups, not shared content."""

MEETING_TITLE = re.compile(r"\b(?:Meet|Zoom|Teams|Webex|Whereby|Jitsi|Huddle|Chime|GoTo)\b", re.IGNORECASE)
"""Browser window titles that show a meeting."""

_MIN_WORDS = 3
_REMEMBERED_LINES = 2000


def meeting_windows(
    windows: Iterable[Any], native: frozenset[str] = NATIVE_MEETING_APPS, browsers: frozenset[str] = BROWSERS
) -> list[Any]:
    """The on-screen ``SCWindow`` objects that show a meeting."""
    chosen = []
    for window in windows:
        app = window.owningApplication()
        bundle = str(app.bundleIdentifier() or "") if app is not None else ""
        frame = window.frame()
        if not window.isOnScreen() or frame.size.width < MIN_WIDTH or frame.size.height < MIN_HEIGHT:
            continue
        if allows(native, bundle) or (allows(browsers, bundle) and MEETING_TITLE.search(str(window.title() or ""))):
            chosen.append(window)
    return chosen


class NewLines:
    """Remembers what was on screen, so each line is checked once per meeting."""

    def __init__(self) -> None:
        self._seen: OrderedDict[str, None] = OrderedDict()

    def __call__(self, lines: Iterable[str]) -> list[str]:
        """The lines not seen before that state a figure (and are more than a label)."""
        fresh = []
        for raw in lines:
            line = " ".join(raw.split())
            key = line.casefold()
            if key in self._seen:
                continue
            self._seen[key] = None
            if len(self._seen) > _REMEMBERED_LINES:
                self._seen.popitem(last=False)
            if len(line.split()) >= _MIN_WORDS and extract_figures(line):
                fresh.append(line)
        return fresh

    def reset(self) -> None:
        self._seen.clear()


def read_text(image: Any) -> list[str]:
    """The lines of text in a ``CGImage``, read on this computer (Vision). Blocks.

    Raises:
        RuntimeError: if text recognition fails.
    """
    import Vision

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["en-US", "tr-TR"])
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"text recognition failed: {error}")
    return [str(result.topCandidates_(1)[0].string()) for result in (request.results() or [])]


async def screen_lines() -> list[str]:
    """The text of every meeting window on screen now.

    Raises:
        PermissionError: if macOS denies Screen Recording access.
    """
    import Quartz
    import ScreenCaptureKit as SCK

    from recall.audio.system_audio import _call

    # Window frames need a WindowServer connection, which this call opens.
    Quartz.CGMainDisplayID()
    content, error = await _call(SCK.SCShareableContent.getShareableContentWithCompletionHandler_)
    if content is None:
        raise PermissionError(f"Screen Recording access is needed to read shared slides ({error})")
    lines: list[str] = []
    for window in meeting_windows(content.windows()):
        frame = window.frame()
        config = SCK.SCStreamConfiguration.alloc().init()
        # Twice the window's size in points, so small slide text is still readable.
        config.setWidth_(int(frame.size.width * 2))
        config.setHeight_(int(frame.size.height * 2))
        window_only = SCK.SCContentFilter.alloc().initWithDesktopIndependentWindow_(window)
        image, error = await _call(
            lambda handler, f=window_only, c=config: SCK.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(f, c, handler)
        )
        if image is None:
            logger.warning("Could not capture a meeting window: %s", error)
            continue
        lines += await asyncio.to_thread(read_text, image)
    return lines


async def watch_slides(
    check: Callable[[Segment], Awaitable[None]],
    read: Callable[[], Awaitable[list[str]]] = screen_lines,
    scan_s: float = SCAN_S,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Every ``scan_s`` seconds, hand each new line with a figure on the meeting window to ``check``.

    Runs until cancelled. A missing Screen Recording permission stops it with a warning.
    """
    new_lines = NewLines()
    started = clock()
    while True:
        try:
            lines = await read()
        except PermissionError as error:
            logger.warning("Slides are not fact-checked: %s", error)
            return
        except Exception:
            logger.exception("Could not read the meeting window")
            lines = []
        for line in new_lines(lines):
            at = clock() - started
            await check(Segment(SOURCE, at, at, line, (), SPEAKER))
        await asyncio.sleep(scan_s)
