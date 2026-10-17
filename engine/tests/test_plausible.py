# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Invented text is recognised; real speech, even mentioning a phrase, is kept."""

import pytest

from recall.audio.plausible import most_likely, phantom, plausible

REAL = ("Bütçe 35 bin dolara düşürüldü.", -0.3, 1.4, 0.01)


@pytest.mark.parametrize(
    "text",
    [
        "Thank you for watching!",
        "Untertitel der Amara.org-Community",
        "Продолжение следует...",
        "ご視聴ありがとうございました",
        "Altyazı M.K.",
        "Sottotitoli creati dalla comunità Amara.org",
        "Bu dizinin betimlemesi TRT tarafından Sesli Betimleme Derneğine yaptırılmıştır.",
        "www.mesetsizlemedernegi.com",
    ],
)
def test_phrases_whisper_invents_in_silence_are_dropped(text: str) -> None:
    assert phantom(text)
    assert not plausible(text, -0.2, 1.2, 0.1)


def test_real_speech_that_mentions_such_a_phrase_is_kept() -> None:
    sentence = "At the end of the webinar the host said thank you for watching and then we discussed the budget for Q3"
    assert not phantom(sentence)
    assert plausible(*REAL)


def test_loops_silence_and_very_unsure_text_are_dropped() -> None:
    assert not plausible("nene " * 60, -0.2, 1.5, 0.0)
    assert not plausible("hmm", -1.2, 1.0, 0.9)  # silence transcribed
    assert not plausible("Clienti kakon nje sbri", -1.8, 1.2, 0.1)


def test_the_choice_stays_within_the_meeting_languages() -> None:
    assert most_likely({"ru": 0.7, "sq": 0.2, "ja": 0.1}, ("tr", "sq", "en")) == "sq"
    assert most_likely({"ru": 0.7}, ()) is None


def test_the_loops_seen_in_a_real_meeting_are_dropped() -> None:
    assert not plausible("I have a lot to do, " * 30, -0.4, 1.8, 0.0)
    assert not plausible("A-D-" * 80, -0.4, 1.8, 0.0)
    assert not plausible("Ich bin ein Mann, " * 30, -0.3, 1.9, 0.0)

