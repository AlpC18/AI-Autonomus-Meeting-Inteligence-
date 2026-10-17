# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Without pyannote installed, the user is told why and what to do."""

from recall.diarization.pyannote_diarizer import missing_extra_message


def test_intel_macs_are_told_it_cannot_work_there() -> None:
    assert "Intel Macs" in missing_extra_message("darwin", "x86_64")


def test_other_platforms_are_told_how_to_install_it() -> None:
    for system, machine in [("darwin", "arm64"), ("win32", "AMD64"), ("linux", "x86_64")]:
        message = missing_extra_message(system, machine)
        assert "Hugging Face token" in message and "uv sync --extra diarization" in message
