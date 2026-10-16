# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Turkish: notes, hints and AI replies in the chosen language; Turkish promises and doubts are noticed."""

from datetime import date

import pytest

from continuum import language
from continuum.context.risk import RiskTracker, Workload, due_date
from continuum.library import summary_of
from continuum.stats import SpeakerStats
from continuum.stats import to_markdown as stats_markdown
from continuum.summarize_cli import split_summary
from continuum.summary import ActionItem, MeetingSummary, to_markdown
from continuum.transcript import Segment

THURSDAY = date(2026, 10, 15)


@pytest.fixture
def turkish(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(language, "_current", "tr")
    yield
    monkeypatch.setattr(language, "_current", None)


def said(text: str, speaker: str = "Ayşe") -> Segment:
    return Segment("system", 1.0, 2.0, text, (), speaker)


def test_notes_are_written_in_turkish(turkish) -> None:
    summary = to_markdown(MeetingSummary("Bütçe onaylandı.", ("Bütçe 35 bin $",), (ActionItem("Raporu gönder", "Ayşe", "2026-11-30"),)))
    assert summary.startswith("## Özet\n")
    assert "### Kararlar" in summary and "- [ ] Raporu gönder (Ayşe, son tarih 2026-11-30)" in summary
    assert stats_markdown([SpeakerStats("Ayşe", 60, 1.0, 30, 0)]).startswith("## Konuşma süreleri\n\n| Konuşan |")


def test_notes_in_either_language_are_read_back() -> None:
    notes = "# Toplantı\n\n- `00:00:01` **Ayşe:** Merhaba.\n\n## Özet\n\nKısa."
    assert summary_of(notes) == "## Özet\n\nKısa."
    assert split_summary(notes) == "# Toplantı\n\n- `00:00:01` **Ayşe:** Merhaba.\n"


@pytest.mark.parametrize(
    ("text", "due"),
    [
        ("Raporu yarın bitireceğim", date(2026, 10, 16)),
        ("Cumaya kadar hallederim", date(2026, 10, 16)),
        ("Cumartesi teslim ederim", date(2026, 10, 17)),
        ("Pazartesiye hazır olur", date(2026, 10, 19)),
        ("Haftaya söz veriyorum", date(2026, 10, 23)),
        ("Ay sonuna kadar biter", date(2026, 10, 31)),
    ],
)
def test_turkish_dates_are_understood(text: str, due: date) -> None:
    assert due_date(text, THURSDAY) == due


def test_turkish_promises_and_doubts_are_tracked_with_turkish_hints(turkish) -> None:
    tracker = RiskTracker(lambda: THURSDAY, lambda speaker, due: Workload(open=12, due_by=4, source="Jira", sprint=9))
    (hint,) = tracker.watch(said("Ödeme API'sini cumaya kadar bitireceğim"))
    assert hint["title"] == "Ayşe bir tarih verdi: 16.10.2026"
    assert hint["body"] == "Ayşe kişisinin 12 açık Jira işi var, 4 tanesi o tarihe kadar bitmeli, 9 tanesi bu sprintte."
    tracker.watch(said("Açıkçası emin değilim, belki yetişmez"))
    report = tracker.finish()
    assert report is not None and "## Taahhütler" in report and "## Tereddütler" in report
    assert "(son tarih 2026-10-16)" in report and "(emin değilim)" in report


def test_ai_replies_are_asked_for_in_the_chosen_language(turkish) -> None:
    class Echo:
        def complete(self, system: str, user: str) -> str:
            return system

    assert language.InLanguage(Echo()).complete("Summarise.", "x").endswith(
        "in Turkish. Keep JSON keys, dates and quoted transcript text unchanged."
    )
    language.use("en")
    assert language.InLanguage(Echo()).complete("Summarise.", "x") == "Summarise."
