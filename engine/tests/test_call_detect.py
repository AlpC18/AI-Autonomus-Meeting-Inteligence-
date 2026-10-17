# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Call detection: reports the microphone state once, then only changes."""

import sys

import pytest

from recall.audio.call_detect import microphone_in_use, watch


def test_only_changes_are_reported() -> None:
    states = iter([False, False, True, True, None, False])
    lines: list[str] = []
    watch(lambda: next(states), lines.append, poll_s=0, rounds=6)
    assert lines == ['{"in_call": false}', '{"in_call": true}', '{"in_call": false}']


@pytest.mark.skipif(sys.platform != "darwin", reason="CoreAudio is macOS only")
def test_the_microphone_state_can_be_read_on_macos() -> None:
    assert microphone_in_use() in (True, False)


def test_windows_counts_a_microphone_use_that_has_not_stopped() -> None:
    from recall.audio.call_detect import any_open_use

    assert any_open_use([(0, 0), (133_000, 133_500), (134_000, 0)]) is True
    assert any_open_use([(0, 0), (133_000, 133_500)]) is False


def test_linux_asks_pulseaudio_for_recording_streams(monkeypatch) -> None:
    import subprocess

    from recall.audio import call_detect

    monkeypatch.setattr(call_detect.shutil, "which", lambda name: "/usr/bin/pactl")
    answers = iter(["42\t1\t17\tPipeWire\ts16le 1ch 48000Hz\n", ""])
    monkeypatch.setattr(
        call_detect.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=next(answers), stderr=""),
    )
    assert call_detect._linux_in_use() is True
    assert call_detect._linux_in_use() is False
    monkeypatch.setattr(call_detect.shutil, "which", lambda name: None)
    assert call_detect._linux_in_use() is None
