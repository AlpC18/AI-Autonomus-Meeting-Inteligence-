# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Timeline titles: from the AI when there is one, else from what was said first."""

from recall.timeline import MAX_TITLE, topic_title


class Llm:
    def __init__(self, reply: str = "", fail: bool = False) -> None:
        self.reply, self.fail, self.prompts = reply, fail, []

    def complete(self, system: str, user: str) -> str:
        self.prompts.append(user)
        if self.fail:
            raise RuntimeError("provider down")
        return self.reply


LINES = ["Bütçe 35 bin dolara düşürüldü.", "Lansman 14 Ekim'de."]


def test_the_ai_names_the_topic() -> None:
    llm = Llm('"Bütçe ve lansman tarihi."\n')
    assert topic_title(LINES, llm) == "Bütçe ve lansman tarihi"
    assert "<lines>" in llm.prompts[0] and "Lansman" in llm.prompts[0]


def test_without_ai_or_when_it_fails_the_first_thing_said_is_the_title() -> None:
    assert topic_title(LINES, None) == "Bütçe 35 bin dolara düşürüldü."
    assert topic_title(LINES, Llm(fail=True)) == "Bütçe 35 bin dolara düşürüldü."
    assert topic_title(LINES, Llm("   ")) == "Bütçe 35 bin dolara düşürüldü."


def test_long_titles_are_cut_at_a_word_and_nothing_said_gives_none() -> None:
    title = topic_title(["word " * 40], None)
    assert len(title) <= MAX_TITLE + 1 and title.endswith("…") and "  " not in title
    assert topic_title(["  "], None) == ""
