# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Windows: only the meeting app is heard, followed as it changes, with all system audio as a fallback."""

import asyncio
import threading

import numpy as np

from continuum.audio import follow
from continuum.audio.blocks import BlockQueue
from continuum.audio.windows_apps import (
    BROWSER_EXES,
    NATIVE_MEETING_EXES,
    Process,
    meeting_process,
)
from continuum.pipeline import _with_fallback

RUNNING = [
    Process(4, 0, "System"),
    Process(100, 4, "chrome.exe"),
    Process(101, 100, "chrome.exe"),  # a tab or the audio service, under the browser
    Process(200, 4, "ms-teams.exe"),
    Process(201, 200, "msedgewebview2.exe"),
    Process(300, 4, "Spotify.exe"),
]


def test_a_native_meeting_app_root_is_preferred_over_a_browser() -> None:
    assert meeting_process(RUNNING, NATIVE_MEETING_EXES, BROWSER_EXES) == Process(200, 4, "ms-teams.exe")
    browser_only = [process for process in RUNNING if process.pid < 200]
    assert meeting_process(browser_only, NATIVE_MEETING_EXES, BROWSER_EXES) == Process(100, 0 + 4, "chrome.exe")
    assert meeting_process(browser_only, NATIVE_MEETING_EXES, frozenset()) is None  # tab extension on


class FakeCapture:
    def __init__(self, pid: int) -> None:
        self.pid, self.closed = pid, False

    def read(self) -> np.ndarray:
        return np.full(800, self.pid / 1000, dtype=np.float32)

    def close(self) -> None:
        self.closed = True


async def test_the_capture_follows_the_meeting_app_and_pads_silence(monkeypatch) -> None:
    monkeypatch.setattr(follow, "APP_REFRESH_S", 0.0)
    choices = iter([None, Process(200, 4, "ms-teams.exe")] + [Process(200, 4, "ms-teams.exe")] * 50)
    opened: list[FakeCapture] = []
    stopped = threading.Event()
    times = iter(i * 0.05 for i in range(10_000))
    queue = BlockQueue("test")
    blocks: list[np.ndarray] = []

    def open_capture(pid: int) -> FakeCapture:
        opened.append(FakeCapture(pid))
        return opened[-1]

    def sleep(_seconds: float) -> None:
        if len(blocks) >= 3:
            stopped.set()

    thread = threading.Thread(
        target=follow.follow_app,
        args=(queue, stopped, lambda: next(choices), open_capture, lambda: lambda: None, lambda: next(times), sleep),
    )
    thread.start()
    async for block in queue:
        blocks.append(block)
        if len(blocks) == 3:
            break
    stopped.set()
    await asyncio.to_thread(thread.join, 2)

    assert [capture.pid for capture in opened] == [200]
    assert all(block.size == 1600 for block in blocks)
    assert blocks[-1][-1] == np.float32(0.2)  # Teams' audio, after the silence while nothing ran


async def test_a_failed_start_falls_back_to_all_system_audio() -> None:
    async def broken():
        raise RuntimeError("process loopback was refused")
        yield

    async def everything():
        yield np.ones(1600, dtype=np.float32)

    assert [block[0] async for block in _with_fallback(broken, everything)] == [1.0]
