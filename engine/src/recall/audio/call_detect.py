# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Notices when a call starts: another app begins using the microphone.

Used by the desktop app's auto-start while the engine is stopped (so any
microphone use is someone else's: Zoom, Meet in a browser, Teams, FaceTime).
Only *whether* the microphone is in use is read; no audio is captured here.
macOS asks CoreAudio, Windows reads the privacy settings' record of which
apps use the microphone now, Linux asks PulseAudio/PipeWire for recording
streams.
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable

POLL_S = 1.0


_CONSENT_KEY = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"


def microphone_in_use() -> bool | None:
    """Whether any process is using the microphone; ``None`` if it cannot be told."""
    if sys.platform == "win32":
        return _windows_in_use()
    if sys.platform.startswith("linux"):
        return _linux_in_use()
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


def any_open_use(uses: Iterable[tuple[int, int]]) -> bool:
    """Whether a ``(LastUsedTimeStart, LastUsedTimeStop)`` record shows use that has not stopped."""
    return any(start > 0 and stop == 0 for start, stop in uses)


def _windows_uses() -> Iterable[tuple[int, int]]:
    import winreg

    def times(key: "winreg.HKEYType") -> tuple[int, int]:
        try:
            return winreg.QueryValueEx(key, "LastUsedTimeStart")[0], winreg.QueryValueEx(key, "LastUsedTimeStop")[0]
        except OSError:
            return 0, 0

    def children(key: "winreg.HKEYType") -> Iterable[str]:
        index = 0
        while True:
            try:
                yield winreg.EnumKey(key, index)
            except OSError:
                return
            index += 1

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CONSENT_KEY) as root:
        for name in list(children(root)):
            with winreg.OpenKey(root, name) as app:
                if name != "NonPackaged":
                    yield times(app)
                    continue
                # Desktop apps (Zoom, Chrome, Teams) are listed one level down.
                for exe in list(children(app)):
                    with winreg.OpenKey(app, exe) as entry:
                        yield times(entry)


def _windows_in_use() -> bool | None:
    try:
        return any_open_use(_windows_uses())
    except OSError:
        return None


def _linux_in_use() -> bool | None:
    # ponytail: any recording stream counts, including a screen recorder's; filter by app if that misfires.
    pactl = shutil.which("pactl")
    if pactl is None:
        return None
    try:
        result = subprocess.run(
            [pactl, "list", "short", "source-outputs"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return bool(result.stdout.strip()) if result.returncode == 0 else None


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
    """Entry point of ``recall-detect-call``; stops when its standard input closes."""
    if microphone_in_use() is None:
        sys.stdout.write(
            json.dumps({"error": "Call detection needs macOS, Windows, or Linux with PulseAudio or PipeWire."}) + "\n"
        )
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
