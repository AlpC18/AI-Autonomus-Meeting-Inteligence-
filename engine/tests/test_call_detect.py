# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Call detection: reports the microphone state once, then only changes."""

import sys

import pytest

from continuum.audio.call_detect import microphone_in_use, watch


def test_only_changes_are_reported() -> None:
    states = iter([False, False, True, True, None, False])
    lines: list[str] = []
    watch(lambda: next(states), lines.append, poll_s=0, rounds=6)
    assert lines == ['{"in_call": false}', '{"in_call": true}', '{"in_call": false}']


@pytest.mark.skipif(sys.platform != "darwin", reason="CoreAudio is macOS only")
def test_the_microphone_state_can_be_read_on_macos() -> None:
    assert microphone_in_use() in (True, False)
