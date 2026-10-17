# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Browser tab audio: only the extension may send it, one tab at a time, and it becomes engine blocks."""

import asyncio
import contextlib
import socket
import sys

import numpy as np
import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from recall.audio.browser_tab import tab_audio_blocks, to_block
from recall.config import Settings

EXTENSION = "chrome-extension://" + "a" * 32


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextlib.asynccontextmanager
async def receiving(**kwargs):
    port = free_port()
    blocks = tab_audio_blocks(port, **kwargs)
    first = asyncio.ensure_future(anext(blocks))
    await asyncio.sleep(0.2)  # let the server start
    try:
        yield port, first, blocks
    finally:
        first.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await first
        await blocks.aclose()


async def test_the_extension_tab_audio_becomes_blocks() -> None:
    samples = np.linspace(-0.5, 0.5, 1600, dtype="<f4")
    async with receiving() as (port, first, _blocks), connect(f"ws://127.0.0.1:{port}", origin=EXTENSION) as tab:
        await tab.send(samples.tobytes())
        block = await asyncio.wait_for(first, 2)
    assert block.dtype == np.float32 and np.allclose(block, samples)


async def test_web_pages_and_other_extensions_cannot_send_audio() -> None:
    async with receiving(extension_id="b" * 32) as (port, _first, _blocks):
        for origin in ("https://evil.example", EXTENSION):
            with pytest.raises(InvalidStatus):
                async with connect(f"ws://127.0.0.1:{port}", origin=origin):
                    pass


async def test_a_second_tab_is_refused_while_one_is_captured() -> None:
    async with (
        receiving() as (port, _first, _blocks),
        connect(f"ws://127.0.0.1:{port}", origin=EXTENSION) as _tab,
        connect(f"ws://127.0.0.1:{port}", origin=EXTENSION) as second,
    ):
        with pytest.raises(ConnectionClosed) as closed:
            await asyncio.wait_for(second.recv(), 2)
    assert closed.value.rcvd is not None and closed.value.rcvd.code == 1008


def test_only_audio_frames_are_accepted_and_clipped() -> None:
    assert to_block("text") is None and to_block(b"abc") is None and to_block(b"") is None
    block = to_block(np.array([2.0, np.nan, -3.0], dtype="<f4").tobytes())
    assert block is not None and block.tolist() == [1.0, 0.0, -1.0]


def test_browser_tab_audio_adds_the_tab_source() -> None:
    settings = Settings.from_env({"RECALL_BROWSER_TAB_AUDIO": "1", "RECALL_BROWSER_EXTENSION_ID": "c" * 32})
    assert settings.sources == ("mic", "system", "tab") and settings.browser_extension_id == "c" * 32
    assert Settings.from_env({}).sources == ("mic", "system")
    with pytest.raises(ValueError, match="RECALL_BROWSER_EXTENSION_ID"):
        Settings.from_env({"RECALL_BROWSER_EXTENSION_ID": "not-an-id"})


@pytest.mark.skipif(sys.platform != "darwin", reason="system audio is filtered per app only on macOS")
def test_with_tab_audio_browsers_are_left_out_of_system_audio() -> None:
    from recall.audio.apps import BROWSERS, MEETING_APPS, NATIVE_MEETING_APPS
    from recall.pipeline import _block_source

    assert _block_source("system", Settings(browser_tab_audio=True)).args == (True, NATIVE_MEETING_APPS)
    assert _block_source("system", Settings(meeting_apps_only=True)).args == (True, MEETING_APPS)
    assert not NATIVE_MEETING_APPS & BROWSERS


async def test_the_firefox_extension_can_send_audio_too() -> None:
    firefox = "moz-extension://1b2c3d4e-0000-4a5b-8c9d-0123456789ab"
    async with receiving() as (port, first, _blocks), connect(f"ws://127.0.0.1:{port}", origin=firefox) as tab:
        await tab.send(np.zeros(1600, dtype="<f4").tobytes())
        assert (await asyncio.wait_for(first, 2)).size == 1600
    assert Settings.from_env({"RECALL_BROWSER_EXTENSION_ID": firefox.removeprefix("moz-extension://")}).browser_extension_id
