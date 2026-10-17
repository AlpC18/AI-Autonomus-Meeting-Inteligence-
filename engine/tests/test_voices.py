# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Voices named in one meeting are recognised in the next."""

import os
import stat
from pathlib import Path

import numpy as np

from recall.diarization.tracker import SpeakerTracker
from recall.diarization.voices import VoiceBook

AYSE = np.array([1.0, 0.0, 0.0])
MARK = np.array([0.0, 1.0, 0.0])


def test_named_voices_survive_a_restart_and_are_recognised(tmp_path: Path) -> None:
    path = tmp_path / "voices.json"
    VoiceBook(path).learn("Ayşe", AYSE * 3)

    book = VoiceBook(path)
    assert book.names == ["Ayşe"]
    assert book.identify(np.array([0.9, 0.2, 0.0])) == "Ayşe"
    assert book.identify(MARK) is None
    if os.name == "posix":  # Windows has no permission bits
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_learning_again_blends_and_forget_removes(tmp_path: Path) -> None:
    book = VoiceBook(tmp_path / "voices.json")
    book.learn("Ayşe", AYSE)
    book.learn("Ayşe", np.array([1.0, 1.0, 0.0]))
    assert book.identify(np.array([1.0, 0.4, 0.0])) == "Ayşe"
    assert book.forget("Ayşe") and not book.forget("Ayşe")
    assert VoiceBook(tmp_path / "voices.json").names == []


def test_bad_files_and_vectors_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "voices.json"
    path.write_text('{"ok": [1, 0, 0], "bad": "x", "": [1], "zero": [0, 0, 0]}')
    book = VoiceBook(path)
    assert book.names == ["ok"]
    assert book.identify(np.zeros(3)) is None
    assert book.identify(np.ones(5)) is None
    path.write_text("not json")
    assert VoiceBook(path).names == []


def test_tracker_gives_the_voice_of_a_session_speaker() -> None:
    tracker = SpeakerTracker()
    assert tracker.name(AYSE, 2.0) == "Speaker 1"
    assert np.allclose(tracker.voice("Speaker 1"), AYSE)
    assert tracker.voice("Speaker 2") is None
    assert tracker.voice("mic") is None
