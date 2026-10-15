# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Notices when a call starts: another app begins using the microphone.

Used by the desktop app's auto-start while the engine is stopped (so any
microphone use is someone else's: Zoom, Meet in a browser, Teams, FaceTime).
Only *whether* the default input device is running is read; no audio is
captured here.
"""

import json
import os
import struct
import sys
import threading
import time
from collections.abc import Callable

POLL_S = 1.0


def microphone_in_use() -> bool | None:
    """Whether any process is using the default input device; ``None`` if unknown.

    Unknown on systems other than macOS, or when CoreAudio does not answer.
    """
    if sys.platform != "darwin":
        return None
    try:
        import CoreAudio as CA
    except ImportError:
        return None

    def read_u32(object_id: int, selector: int) -> int | None:
        address = CA.AudioObjectPropertyAddress(
            selector, CA.kAudioObjectPropertyScopeGlobal, CA.kAudioObjectPropertyElementMain
        )
        status, size, data = CA.AudioObjectGetPropertyData(object_id, address, 0, [], 4, bytearray(4))
        return struct.unpack("<I", bytes(data)[:4])[0] if status == 0 and size == 4 else None

    try:
        device = read_u32(CA.kAudioObjectSystemObject, CA.kAudioHardwarePropertyDefaultInputDevice)
        if not device:
            return None
        running = read_u32(device, CA.kAudioDevicePropertyDeviceIsRunningSomewhere)
    except (TypeError, ValueError, OSError, struct.error):
        # PyObjC reports a refused or malformed CoreAudio call this way.
        return None
    return None if running is None else running != 0


def watch(
    probe: Callable[[], bool | None],
    emit: Callable[[str], None],
    poll_s: float = POLL_S,
    rounds: int | None = None,
) -> None:
    """Emit ``{"in_call": ...}`` once at start and then whenever the answer changes."""
    last: bool | None = None
    first = True
    count = 0
    while rounds is None or count < rounds:
        count += 1
        state = bool(probe())
        if first or state != last:
            emit(json.dumps({"in_call": state}))
            first, last = False, state
        if rounds is None or count < rounds:
            time.sleep(poll_s)


def main() -> None:
    """Entry point of ``continuum-detect-call``; stops when its standard input closes."""
    if microphone_in_use() is None:
        sys.stdout.write(json.dumps({"error": "Call detection is only available on macOS."}) + "\n")
        sys.exit(1)

    def stop_with_parent() -> None:
        while sys.stdin.buffer.read(4096):
            pass
        # The app is gone; nothing needs cleaning up, so leave at once.
        os._exit(0)

    threading.Thread(target=stop_with_parent, daemon=True).start()

    def emit(line: str) -> None:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    try:
        watch(microphone_in_use, emit)
    except (KeyboardInterrupt, BrokenPipeError):
        return


if __name__ == "__main__":
    main()
