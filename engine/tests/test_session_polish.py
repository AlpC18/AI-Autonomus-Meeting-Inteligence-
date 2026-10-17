# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""After a meeting, the accurate transcript replaces the live one everywhere."""

from dataclasses import replace
from pathlib import Path

import numpy as np
from test_session import FakeLlm, FakeMemory, make, said

from recall.config import Settings
from recall.privacy import storage_settings
from recall.session import MeetingSession


class ForgettingMemory(FakeMemory):
    def __init__(self) -> None:
        super().__init__()
        self.forgotten: list[str] = []

    def forget_meeting(self, meeting_id: str) -> None:
        self.forgotten.append(meeting_id)
        self.stored = [entry for entry in self.stored if entry[1] != meeting_id]


async def finish_polishing(session: MeetingSession) -> None:
    for task in list(session._polishing):
        await task
    await session.close()  # the next meeting's temporary recording goes with it


async def test_the_accurate_transcript_replaces_the_live_one(tmp_path: Path) -> None:
    recordings: list[Path] = []

    def polish(path: Path, spans: list[tuple[float, float]]) -> list[list[tuple[float, float, str]]]:
        recordings.append(path)
        assert path.exists()
        # 3 s of the first (silent) meeting came before this recording started.
        assert spans == [(1.0, 2.0)]
        return [[(0.9, 2.1, "Bütçe 35 bin dolara düşürüldü.")]]

    memory, llm = ForgettingMemory(), FakeLlm()
    session, _published, events = await make(tmp_path, memory=memory, llm=llm, polish=polish)
    session.record("system", np.zeros(48_000, dtype=np.float32))
    await session.end()  # nobody spoke: nothing to polish; the next meeting starts 3 s in

    session.record("system", np.full(64_000, 0.1, dtype=np.float32))
    live = said("Büyükçe 35 bin dolara düşürürdü", start=4.0)
    session.publish(live)
    session.remember(live, disputed=True)
    await session.end()
    await finish_polishing(session)

    notes = next((tmp_path / "notes").glob("*.md")).read_text(encoding="utf-8")
    assert "Bütçe 35 bin dolara düşürüldü." in notes and "Büyükçe" not in notes
    assert [(segment.text, disputed) for segment, _id, disputed in memory.stored] == [
        ("Bütçe 35 bin dolara düşürüldü.", True)
    ]
    assert "Bütçe 35 bin dolara düşürüldü." in llm.calls[-1]
    kinds = [event["type"] for event in events]
    assert kinds.index("polished") < kinds.index("summary")
    assert not recordings[-1].exists() and not recordings[-1].parent.exists()


async def test_a_failed_redo_keeps_the_live_transcript_and_still_summarises(tmp_path: Path) -> None:
    def polish(_path: Path, _spans: list[tuple[float, float]]) -> list[list[tuple[float, float, str]]]:
        raise RuntimeError("model download failed")

    llm = FakeLlm()
    session, _published, events = await make(tmp_path, llm=llm, polish=polish)
    session.record("system", np.full(32_000, 0.1, dtype=np.float32))
    session.publish(said("Budget is 35,000"))
    await session.end()
    await finish_polishing(session)

    assert "Budget is 35,000" in llm.calls[-1]
    assert {"type": "polished", "improved": False} in events
    assert "summary" in [event["type"] for event in events]


def test_nothing_is_recorded_for_it_when_storing_is_not_allowed(monkeypatch) -> None:
    monkeypatch.setattr("recall.privacy.disk_encryption_active", lambda: False)
    settings = replace(Settings(notes_dir=Path("/tmp/n")), require_disk_encryption=True)
    assert storage_settings(settings).final_model is None
