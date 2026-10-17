# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Meeting templates: a standup, 1:1, sales call, interview or retro gets its own summary sections."""

import json

import pytest

from recall import language
from recall.config import Settings
from recall.summary import follow_up_email, summarize, to_markdown
from recall.templates import choose

STANDUP = json.dumps(
    {
        "overview": "Daily sync.",
        "decisions": [],
        "action_items": [],
        "sections": {"done": ["Ana shipped the login page"], "next": [], "blockers": ["Bob waits for API keys"], "extra": ["x"]},
    }
)


class Model:
    def __init__(self, reply: str) -> None:
        self.reply, self.system = reply, ""

    def complete(self, system: str, user: str) -> str:
        self.system = system
        return self.reply


@pytest.mark.parametrize(
    ("title", "template"),
    [
        ("Daily standup", "standup"),
        ("1:1 with Ana", "one_on_one"),
        ("Birebir - Ayşe", "one_on_one"),
        ("Interview: backend engineer", "interview"),
        ("Sprint 14 retro", "retro"),
        ("Acme demo", "sales"),
        ("Budget review", None),
        (None, None),
    ],
)
def test_the_kind_of_meeting_comes_from_its_title(title: str | None, template: str | None) -> None:
    assert choose("auto", title) == template


def test_a_setting_overrides_the_title() -> None:
    assert choose("sales", "Daily standup") == "sales"
    assert choose("general", "Daily standup") is None


def test_a_standup_is_summarised_with_its_sections() -> None:
    model = Model(STANDUP)
    summary = summarize("- `00:00:01` **Ana:** I shipped the login page.", model, template="standup")

    assert '"sections": {"done": ["..."], "next": ["..."], "blockers": ["..."]}' in model.system
    assert summary.sections == (("Done", ("Ana shipped the login page",)), ("Blockers", ("Bob waits for API keys",)))
    markdown = to_markdown(summary)
    assert "### Done\n\n- Ana shipped the login page" in markdown and "### Blockers" in markdown and "### Next" not in markdown
    assert "Blockers\n- Bob waits for API keys" in follow_up_email(summary)[1]


def test_a_general_meeting_has_no_sections() -> None:
    model = Model(STANDUP)
    assert summarize("Ana: hello", model).sections == ()
    assert '"sections"' not in model.system


def test_sections_are_headed_in_turkish(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(language, "_current", "tr")
    assert "### Engeller" in to_markdown(summarize("Ana: merhaba", Model(STANDUP), template="standup"))


def test_the_template_setting_is_checked() -> None:
    assert Settings.from_env({"RECALL_MEETING_TEMPLATE": "Retro"}).meeting_template == "retro"
    with pytest.raises(ValueError, match="RECALL_MEETING_TEMPLATE"):
        Settings.from_env({"RECALL_MEETING_TEMPLATE": "party"})
