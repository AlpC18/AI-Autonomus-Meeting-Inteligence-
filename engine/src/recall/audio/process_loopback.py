# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.
# ruff: noqa: RUF012 - comtypes reads _methods_ and _com_interfaces_ as plain class lists

"""Captures only the meeting app's audio on Windows (WASAPI process loopback).

Windows 10 version 2004 and later can record what one process and its
children play. The meeting app is chosen with
:func:`recall.audio.windows_apps.meeting_process` and re-checked every
few seconds, so a call that moves from the browser to Teams is followed.
While no meeting app runs, silence is produced. Uses ``comtypes`` (Windows
only); when process loopback is unavailable, the caller falls back to all
system audio.
"""

import asyncio
import ctypes
import functools
import logging
import threading
from collections.abc import AsyncIterator, Callable
from ctypes import POINTER, byref, c_int, c_uint32, c_uint64, c_void_p, wintypes
from typing import Any

import numpy as np

from recall.audio.blocks import SAMPLE_RATE, BlockQueue
from recall.audio.follow import follow_app
from recall.audio.windows_apps import Process, meeting_process, running_processes

logger = logging.getLogger(__name__)

_BUFFER_HNS = 2_000_000  # 200 ms, in 100-ns units
_ACTIVATE_TIMEOUT_S = 5.0

_LOOPBACK_DEVICE = "VAD\\Process_Loopback"
_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
_INCLUDE_TARGET_PROCESS_TREE = 0
_VT_BLOB = 65
_STREAMFLAGS = 0x00020000 | 0x80000000 | 0x08000000  # LOOPBACK | AUTOCONVERTPCM | SRC_DEFAULT_QUALITY
_SILENT = 0x2


@functools.cache
def _interfaces() -> dict[str, Any]:
    """The COM declarations, built on first use (``comtypes`` exists only on Windows)."""
    import comtypes
    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

    class IActivateAudioInterfaceAsyncOperation(IUnknown):
        _iid_ = GUID("{72A22D78-CDE4-431D-B8CC-843A71199B6D}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetActivateResult",
                      (["out"], POINTER(ctypes.c_long), "activateResult"),
                      (["out"], POINTER(POINTER(IUnknown)), "activatedInterface")),
        ]

    class IActivateAudioInterfaceCompletionHandler(IUnknown):
        _iid_ = GUID("{41D949AB-9862-444A-80F6-C261334DA5EB}")
        _methods_ = [
            COMMETHOD([], HRESULT, "ActivateCompleted",
                      (["in"], POINTER(IActivateAudioInterfaceAsyncOperation), "operation")),
        ]

    class IAgileObject(IUnknown):
        _iid_ = GUID("{94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90}")
        _methods_: list = []

    class IAudioCaptureClient(IUnknown):
        _iid_ = GUID("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetBuffer",
                      (["out"], POINTER(c_void_p), "data"),
                      (["out"], POINTER(c_uint32), "frames"),
                      (["out"], POINTER(wintypes.DWORD), "flags"),
                      (["out"], POINTER(c_uint64), "position"),
                      (["out"], POINTER(c_uint64), "qpc")),
            COMMETHOD([], HRESULT, "ReleaseBuffer", (["in"], c_uint32, "frames")),
            COMMETHOD([], HRESULT, "GetNextPacketSize", (["out"], POINTER(c_uint32), "frames")),
        ]

    class IAudioClient(IUnknown):
        _iid_ = GUID("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
        _methods_ = [
            COMMETHOD([], HRESULT, "Initialize",
                      (["in"], c_int, "shareMode"), (["in"], wintypes.DWORD, "flags"),
                      (["in"], ctypes.c_longlong, "bufferDuration"), (["in"], ctypes.c_longlong, "periodicity"),
                      (["in"], c_void_p, "format"), (["in"], c_void_p, "sessionGuid")),
            COMMETHOD([], HRESULT, "GetBufferSize", (["out"], POINTER(c_uint32), "frames")),
            COMMETHOD([], HRESULT, "GetStreamLatency", (["out"], POINTER(ctypes.c_longlong), "latency")),
            COMMETHOD([], HRESULT, "GetCurrentPadding", (["out"], POINTER(c_uint32), "frames")),
            COMMETHOD([], HRESULT, "IsFormatSupported", (["in"], c_int, "mode"), (["in"], c_void_p, "format"),
                      (["out"], POINTER(c_void_p), "closest")),
            COMMETHOD([], HRESULT, "GetMixFormat", (["out"], POINTER(c_void_p), "format")),
            COMMETHOD([], HRESULT, "GetDevicePeriod", (["out"], POINTER(ctypes.c_longlong), "default"),
                      (["out"], POINTER(ctypes.c_longlong), "minimum")),
            COMMETHOD([], HRESULT, "Start"),
            COMMETHOD([], HRESULT, "Stop"),
            COMMETHOD([], HRESULT, "Reset"),
            COMMETHOD([], HRESULT, "SetEventHandle", (["in"], wintypes.HANDLE, "event")),
            COMMETHOD([], HRESULT, "GetService", (["in"], POINTER(GUID), "iid"),
                      (["out"], POINTER(c_void_p), "service")),
        ]

    class Done(comtypes.COMObject):
        _com_interfaces_ = [IActivateAudioInterfaceCompletionHandler, IAgileObject]

        def __init__(self) -> None:
            super().__init__()
            self.finished = threading.Event()

        def ActivateCompleted(self, operation: Any) -> int:
            self.finished.set()
            return 0

    return {
        "comtypes": comtypes, "GUID": GUID, "IUnknown": IUnknown, "Done": Done,
        "IActivateAudioInterfaceAsyncOperation": IActivateAudioInterfaceAsyncOperation,
        "IActivateAudioInterfaceCompletionHandler": IActivateAudioInterfaceCompletionHandler,
        "IAudioClient": IAudioClient, "IAudioCaptureClient": IAudioCaptureClient,
    }


class _LoopbackParams(ctypes.Structure):
    _fields_ = (("TargetProcessId", wintypes.DWORD), ("ProcessLoopbackMode", c_int))


class _ActivationParams(ctypes.Structure):
    _fields_ = (("ActivationType", c_int), ("ProcessLoopbackParams", _LoopbackParams))


class _Blob(ctypes.Structure):
    _fields_ = (("cbSize", wintypes.ULONG), ("pBlobData", c_void_p))


class _PropVariant(ctypes.Structure):
    _fields_ = (("vt", wintypes.USHORT), ("r1", wintypes.WORD), ("r2", wintypes.WORD), ("r3", wintypes.WORD),
                ("blob", _Blob))


class _WaveFormat(ctypes.Structure):
    _pack_ = 1
    _fields_ = (("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", wintypes.DWORD),
                ("nAvgBytesPerSec", wintypes.DWORD), ("nBlockAlign", wintypes.WORD),
                ("wBitsPerSample", wintypes.WORD), ("cbSize", wintypes.WORD))


class _Capture:
    """One process tree's audio as 16 kHz mono 16-bit samples."""

    def __init__(self, pid: int) -> None:
        com = _interfaces()
        params = _ActivationParams(_ACTIVATION_TYPE_PROCESS_LOOPBACK, _LoopbackParams(pid, _INCLUDE_TARGET_PROCESS_TREE))
        variant = _PropVariant(_VT_BLOB, 0, 0, 0, _Blob(ctypes.sizeof(params), ctypes.cast(byref(params), c_void_p)))
        handler = com["Done"]()
        operation = POINTER(com["IActivateAudioInterfaceAsyncOperation"])()
        activate = ctypes.WinDLL("Mmdevapi").ActivateAudioInterfaceAsync
        activate.restype = ctypes.HRESULT
        activate(
            ctypes.c_wchar_p(_LOOPBACK_DEVICE),
            byref(com["IAudioClient"]._iid_),
            byref(variant),
            handler.QueryInterface(com["IActivateAudioInterfaceCompletionHandler"]),
            byref(operation),
        )
        if not handler.finished.wait(_ACTIVATE_TIMEOUT_S):
            raise RuntimeError("Windows did not activate process loopback in time")
        result, unknown = operation.GetActivateResult()
        if result != 0:
            raise RuntimeError(f"process loopback was refused (HRESULT {result & 0xFFFFFFFF:#010x})")
        self._client = unknown.QueryInterface(com["IAudioClient"])
        wave = _WaveFormat(1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16, 0)
        self._client.Initialize(0, _STREAMFLAGS, _BUFFER_HNS, 0, ctypes.cast(byref(wave), c_void_p), None)
        service = self._client.GetService(byref(com["IAudioCaptureClient"]._iid_))
        self._capture = ctypes.cast(service, POINTER(com["IAudioCaptureClient"]))
        self._client.Start()

    def read(self) -> np.ndarray:
        """Every sample available now, as float32 in [-1, 1]."""
        chunks = []
        while self._capture.GetNextPacketSize() > 0:
            data, frames, flags, _position, _qpc = self._capture.GetBuffer()
            if flags & _SILENT or not data:
                chunks.append(np.zeros(frames, dtype=np.float32))
            else:
                raw = ctypes.string_at(data, frames * 2)
                chunks.append(np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0)
            self._capture.ReleaseBuffer(frames)
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    def close(self) -> None:
        self._client.Stop()


def _com_apartment() -> Callable[[], None]:
    """Join the multithreaded COM apartment; returns how to leave it."""
    import comtypes

    comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    return comtypes.CoUninitialize


async def process_loopback_blocks(native: frozenset[str], browsers: frozenset[str]) -> AsyncIterator[np.ndarray]:
    """Yield 100 ms mono float32 blocks of the meeting app's audio.

    ``native`` and ``browsers`` are the executable names to hear (a native
    app is preferred). Runs until the consumer stops iterating.

    Raises:
        RuntimeError: if process loopback is unavailable (the caller then hears all system audio).
    """
    try:
        import comtypes  # noqa: F401
    except ImportError as error:
        raise RuntimeError("process loopback needs the 'comtypes' package") from error
    queue = BlockQueue("Meeting app")
    stopped = threading.Event()

    def choose() -> Process | None:
        return meeting_process(running_processes(), native, browsers)

    thread = threading.Thread(
        target=follow_app, args=(queue, stopped, choose, _Capture, _com_apartment), name="process-loopback", daemon=True
    )
    thread.start()
    try:
        async for block in queue:
            yield block
    finally:
        stopped.set()
        await asyncio.to_thread(thread.join, 2)
