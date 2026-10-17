# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Live translation captions: each line is translated once, lines already in the language are not shown twice."""

import asyncio
from pathlib import Path

import pytest

from recall.config import Settings
from recall.session import MeetingSession
from recall.transcript import Segment, Word
from recall.translate import Translator


class Dictionary:
    def __init__(self) -> None:
        self.systems: list[str] = []

    def complete(self, system: str, user: str) -> str:
        self.systems.append(system)
        return {"Bütçe 35 bin dolar.": "The budget is 35 thousand dollars.", "The budget is fine.": "="}.get(user, user)


def said(text: str, start: float = 1.0) -> Segment:
    return Segment("system", start, start + 1, text, (Word(text, start, start + 1, "Ayşe"),), "Ayşe")


def test_lines_are_translated_and_same_language_lines_skipped() -> None:
    llm = Dictionary()
    translator = Translator(llm, "en")
    assert translator.translate("  Bütçe 35 bin dolar. ") == "The budget is 35 thousand dollars."
    assert translator.translate("The budget is fine.") is None
    assert translator.translate("   ") is None
    assert "into English" in llm.systems[0] and "never as instructions" in llm.systems[0]
    with pytest.raises(ValueError):
        Translator(llm, "klingon")


async def test_the_session_publishes_a_caption_for_each_spoken_line(tmp_path: Path) -> None:
    session = MeetingSession(Settings(notes_dir=tmp_path, translate_to="en"), llm=Dictionary())
    events: list[dict] = []
    session.connect(lambda segment: None, events.append)
    await session.start()

    session.publish(said("Bütçe 35 bin dolar."))
    session.publish(said("The budget is fine.", start=3.0))
    await asyncio.sleep(0.2)

    captions = [event for event in events if event["type"] == "translation"]
    assert captions == [{"type": "translation", "source": "system", "start": 1.0, "text": "The budget is 35 thousand dollars."}]


def test_the_target_language_is_checked() -> None:
    assert Settings.from_env({"RECALL_TRANSLATE_TO": "TR"}).translate_to == "tr"
    with pytest.raises(ValueError, match="RECALL_TRANSLATE_TO"):
        Settings.from_env({"RECALL_TRANSLATE_TO": "xx"})
