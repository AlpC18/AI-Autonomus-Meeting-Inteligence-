# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Redaction: personal data and secrets never reach storage; money and dates do."""

import pytest

from recall.factcheck.figures import extract_figures
from recall.privacy import redact, redact_segment
from recall.transcript import Segment, Word


@pytest.mark.parametrize(
    ("said", "stored"),
    [
        ("Mail me at ana.kaya+work@acme.co.uk please", "Mail me at [email] please"),
        ("Call me on +90 532 123 45 67 tomorrow", "Call me on [phone number] tomorrow"),
        ("my number is 555-123-4567", "my number is [phone number]"),
        ("card 4111 1111 1111 1111 expires soon", "card [card number] expires soon"),
        ("IBAN TR33 0006 1005 1978 6457 8413 26 please", "IBAN [iban] please"),
        ("the key is sk-ant-api03-abcdefghijklmnop", "the key is [secret]"),
        ("token ghp_abcdefghijklmnopqrstuvwxyz1234", "token [secret]"),
        ("the wifi password is Sunflower42", "the wifi password is [secret]"),
        ("şifre: 4821 olsun", "şifre: [secret] olsun"),
        ("the password: hunter2", "the password: [secret]"),
    ],
)
def test_personal_data_and_secrets_are_replaced(said: str, stored: str) -> None:
    assert redact(said) == stored


@pytest.mark.parametrize(
    "said",
    [
        "The budget is $35,000 for Q4",
        "We spent 1,250,000 dollars last year",
        "Revenue grew 12.5% to 4.2 million",
        "Deadline is 2026-11-30",
        "Meet at 10:30 in room 4",
        "We need the password reset flow fixed",
        "Order 12345678 shipped",
        "the budget is 35000000 lira",
    ],
)
def test_money_dates_and_ordinary_numbers_are_kept(said: str) -> None:
    assert redact(said) == said


def test_fact_check_figures_survive_redaction() -> None:
    said = "Budget is $50,000, call 555-123-4567"
    assert extract_figures(redact(said)) == extract_figures("Budget is $50,000")


def test_segment_text_and_words_are_redacted_with_timings_kept() -> None:
    segment = Segment(
        "mic",
        0.0,
        2.0,
        "email ana@acme.io now",
        (Word("email", 0.0, 0.5, "me"), Word("ana@acme.io", 0.5, 1.5, "me"), Word("now", 1.5, 2.0, "me")),
        "me",
    )

    clean = redact_segment(segment)

    assert clean.text == "email [email] now"
    assert [word.text for word in clean.words] == ["email", "[email]", "now"]
    assert [word.start for word in clean.words] == [0.0, 0.5, 1.5]
    assert redact_segment(clean) is clean


def test_nothing_is_stored_when_required_encryption_is_off(monkeypatch, tmp_path) -> None:
    from recall import privacy
    from recall.config import Settings
    from recall.memory.scope import TenantScope

    wanted = Settings(
        notes_dir=tmp_path, scope=TenantScope("acme", "web"), record_audio=True, require_disk_encryption=True
    )
    monkeypatch.setattr(privacy, "disk_encryption_active", lambda: False)
    off = privacy.storage_settings(wanted)
    assert (off.notes_dir, off.scope, off.record_audio, off.remember_voices) == (None, None, False, False)

    monkeypatch.setattr(privacy, "disk_encryption_active", lambda: None)  # cannot be told
    assert privacy.storage_settings(wanted).notes_dir is None

    monkeypatch.setattr(privacy, "disk_encryption_active", lambda: True)
    assert privacy.storage_settings(wanted) == wanted
    monkeypatch.setattr(privacy, "disk_encryption_active", lambda: False)
    assert privacy.storage_settings(Settings(notes_dir=tmp_path)).notes_dir == tmp_path
