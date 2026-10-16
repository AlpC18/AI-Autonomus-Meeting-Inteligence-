# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Captures system audio (what plays through the speakers) on macOS.

Uses ScreenCaptureKit, so no virtual audio driver or meeting bot is needed.
macOS requires the Screen Recording permission for the app running the engine.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

import CoreMedia
import dispatch
import numpy as np
import objc
import ScreenCaptureKit as SCK
from Foundation import NSObject

from continuum.audio.apps import bundle_ids, meeting_apps
from continuum.audio.blocks import SAMPLE_RATE, BlockQueue

logger = logging.getLogger(__name__)

APP_REFRESH_S = 10.0
"""How often the set of meeting apps is re-read when only they are heard."""

_CALLBACK_TIMEOUT_S = 15.0
_QUEUE_BLOCKS = 3000  # ScreenCaptureKit delivers 20 ms buffers: about one minute.
_PERMISSION_HELP = (
    "System audio capture was refused. Allow Screen Recording for the app running "
    "the engine in System Settings > Privacy & Security > Screen & System Audio "
    "Recording, then restart it."
)


class _StreamReceiver(NSObject):
    """Objective-C delegate that forwards audio buffers and stream failures."""

    def initWithQueue_(self, queue: BlockQueue) -> "_StreamReceiver":
        self = objc.super(_StreamReceiver, self).init()  # noqa: PLW0642 - PyObjC init rebinds self
        if self is not None:
            self._queue = queue
        return self

    def stream_didOutputSampleBuffer_ofType_(
        self, _stream: Any, sample_buffer: Any, output_type: int
    ) -> None:
        if output_type != SCK.SCStreamOutputTypeAudio:
            return
        block_buffer = CoreMedia.CMSampleBufferGetDataBuffer(sample_buffer)
        if block_buffer is None:
            return
        length = CoreMedia.CMBlockBufferGetDataLength(block_buffer)
        status, data = CoreMedia.CMBlockBufferCopyDataBytes(block_buffer, 0, length, None)
        if status != 0:
            return
        self._queue.put_threadsafe(np.frombuffer(bytes(data), dtype=np.float32).copy())

    def stream_didStopWithError_(self, _stream: Any, error: Any) -> None:
        self._queue.fail_threadsafe(
            RuntimeError(f"System audio capture stopped unexpectedly: {error}")
        )


async def _call(start: Callable[[Callable[..., None]], None]) -> tuple[Any, ...]:
    """Run a completion-handler API and await the handler's arguments."""
    loop = asyncio.get_running_loop()
    done: asyncio.Future[tuple[Any, ...]] = loop.create_future()

    def handler(*args: Any) -> None:
        loop.call_soon_threadsafe(done.set_result, args)

    start(handler)
    return await asyncio.wait_for(done, _CALLBACK_TIMEOUT_S)


def _content_filter(display: Any, apps: list[Any] | None) -> Any:
    """Everything on ``display``, or only the audio of ``apps`` when given."""
    if apps is None:
        return SCK.SCContentFilter.alloc().initWithDisplay_excludingWindows_(display, [])
    return SCK.SCContentFilter.alloc().initWithDisplay_includingApplications_exceptingWindows_(
        display, apps, []
    )


async def _follow_meeting_apps(stream: Any, heard: frozenset[str]) -> None:
    """Keep the capture on the meeting apps running now, as they open and close."""
    while True:
        await asyncio.sleep(APP_REFRESH_S)
        content, _error = await _call(
            SCK.SCShareableContent.getShareableContentWithCompletionHandler_
        )
        if content is None or not content.displays():
            continue
        apps = meeting_apps(content.applications())
        if bundle_ids(apps) == heard:
            continue
        content_filter = _content_filter(content.displays()[0], apps)
        (error,) = await _call(
            lambda handler, f=content_filter: stream.updateContentFilter_completionHandler_(f, handler)
        )
        if error is None:
            heard = bundle_ids(apps)
            logger.info("Hearing meeting apps: %s", ", ".join(sorted(heard)) or "none running")


async def system_audio_blocks(only_meeting_apps: bool = False) -> AsyncIterator[np.ndarray]:
    """Yield mono float32 blocks at 16 kHz of what the machine plays.

    With ``only_meeting_apps`` only the audio of running meeting apps and
    browsers is captured (see :data:`continuum.audio.apps.MEETING_APPS`), so
    music or videos in other apps stay out of the transcript. The engine's own
    audio output is always excluded. Runs until the consumer stops iterating,
    then stops the capture.

    Raises:
        PermissionError: if macOS denies Screen Recording access.
        RuntimeError: if no display is available, the capture cannot start, or
            it stops unexpectedly while running.
        TimeoutError: if macOS does not answer within 15 seconds.
    """
    content, error = await _call(
        SCK.SCShareableContent.getShareableContentWithCompletionHandler_
    )
    if content is None:
        raise PermissionError(f"{_PERMISSION_HELP} (macOS said: {error})")
    displays = content.displays()
    if not displays:
        raise RuntimeError("System audio capture needs a display, and none was found.")

    # Video is required by the API but unused, so it is kept as small as allowed.
    config = SCK.SCStreamConfiguration.alloc().init()
    config.setCapturesAudio_(True)
    config.setSampleRate_(SAMPLE_RATE)
    config.setChannelCount_(1)
    config.setExcludesCurrentProcessAudio_(True)
    config.setWidth_(2)
    config.setHeight_(2)

    queue = BlockQueue("System", max_blocks=_QUEUE_BLOCKS)
    receiver = _StreamReceiver.alloc().initWithQueue_(queue)
    apps = meeting_apps(content.applications()) if only_meeting_apps else None
    content_filter = _content_filter(displays[0], apps)
    stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(
        content_filter, config, receiver
    )
    added, error = stream.addStreamOutput_type_sampleHandlerQueue_error_(
        receiver,
        SCK.SCStreamOutputTypeAudio,
        dispatch.dispatch_queue_create(b"continuum.system-audio", None),
        None,
    )
    if not added:
        raise RuntimeError(f"Could not attach to system audio: {error}")

    (error,) = await _call(stream.startCaptureWithCompletionHandler_)
    if error is not None:
        raise RuntimeError(f"Could not start system audio capture: {error}")
    following = None
    if apps is not None:
        logger.info("Hearing meeting apps: %s", ", ".join(sorted(bundle_ids(apps))) or "none running")
        following = asyncio.create_task(_follow_meeting_apps(stream, bundle_ids(apps)))
    try:
        async for block in queue:
            yield block
    finally:
        if following is not None:
            following.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await following
        await _call(stream.stopCaptureWithCompletionHandler_)
