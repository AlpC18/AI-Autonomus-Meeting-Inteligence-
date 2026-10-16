# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Which running Windows process is the meeting, for capturing only its audio.

The counterpart of :mod:`continuum.audio.apps` (macOS bundle IDs), by
executable name. Process loopback captures one process and its children, so
the meeting app's root process is chosen: the one whose parent is not the
same program (Chrome and Teams run many processes under one root).
"""

import ctypes
import sys
from collections.abc import Iterable
from dataclasses import dataclass

NATIVE_MEETING_EXES = frozenset(
    {
        "ms-teams.exe",
        "teams.exe",
        "zoom.exe",
        "slack.exe",
        "webex.exe",
        "ciscocollabhost.exe",
        "webexmta.exe",
        "discord.exe",
        "whatsapp.exe",
        "skype.exe",
        "lync.exe",
        "telegram.exe",
        "signal.exe",
        "viber.exe",
        "wechat.exe",
        "line.exe",
        "gotomeeting.exe",
        "g2mcomm.exe",
        "ringcentral.exe",
        "jitsi meet.exe",
        "element.exe",
        "amazon chime.exe",
    }
)
"""Executables of meeting apps other than browsers (lower case)."""

BROWSER_EXES = frozenset(
    {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe", "arc.exe"}
)
"""Browsers, for calls in a tab; all their tabs are heard."""


@dataclass(frozen=True, slots=True)
class Process:
    pid: int
    parent: int
    name: str


def meeting_process(
    processes: Iterable[Process], native: frozenset[str], browsers: frozenset[str]
) -> Process | None:
    """The root process of the meeting app to hear: a native app before a browser; ``None`` if none runs.

    ``native`` and ``browsers`` are lower-case executable names.
    """
    running = list(processes)
    names = {process.pid: process.name.lower() for process in running}
    roots = [
        process
        for process in running
        if process.name.lower() in native | browsers and names.get(process.parent) != process.name.lower()
    ]
    # ponytail: one app at a time; mixing two meeting apps' streams is rarely needed.
    for group in (native, browsers):
        found = sorted((process for process in roots if process.name.lower() in group), key=lambda p: p.pid)
        if found:
            return found[0]
    return None


class _ProcessEntry(ctypes.Structure):
    _fields_ = (
        ("dwSize", ctypes.c_uint32),
        ("cntUsage", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", ctypes.c_uint32),
        ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_wchar * 260),
    )


def running_processes() -> list[Process]:
    """Every process with its parent, from a Toolhelp snapshot (Windows only).

    Raises:
        OSError: if the snapshot cannot be taken.
    """
    if sys.platform != "win32":
        raise OSError("process snapshots need Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if snapshot in (None, ctypes.c_void_p(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(_ProcessEntry)
        found = []
        more = kernel32.Process32FirstW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
        while more:
            found.append(Process(entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile))
            more = kernel32.Process32NextW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
        return found
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(snapshot))
