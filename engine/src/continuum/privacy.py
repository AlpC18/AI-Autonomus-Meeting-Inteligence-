# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Keeps personal data and secrets out of what Continuum stores.

:func:`redact` replaces e-mail addresses, phone and card numbers, IBANs,
API keys and spoken passwords with placeholders before a transcript is
written to memory or to the Markdown notes. The live transcript on screen
is not changed. Amounts of money, percentages and dates are left alone, so
fact checking keeps working.
"""

import logging
import re
import subprocess
import sys
from dataclasses import replace
from typing import TYPE_CHECKING

from continuum.transcript import Segment

if TYPE_CHECKING:
    from continuum.config import Settings

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_SECRET = re.compile(
    r"\b(?:sk-ant-[\w-]{10,}|(?:sk|pk|rk)-[\w-]{16,}|gh[pousr]_\w{20,}|github_pat_\w{20,}"
    r"|xox[abposr]-[\w-]{10,}|AKIA[0-9A-Z]{16}|AIza[\w-]{35}|gsk_\w{20,}"
    r"|eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,})"
)
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b")
_PASSWORD = re.compile(
    r"(?i)\b(password|passcode|pin code|pin|şifre(?:si|m)?|parola(?:sı|m)?)"
    r"(\s*(?:is|was|:|=|is:)\s*|\s+)([^\s,.;]*\d[^\s,.;]*|(?<=is )\S+|(?<=: )\S+|(?<==)\S+)"
)
# A run of digits with the separators people use in phone and card numbers.
_DIGITS = re.compile(r"(?<![\w$€£₺%.,])\+?\d(?:[ ().-]?\d){7,22}(?![\w%])")
_CURRENCY_AFTER = re.compile(r"^\s*(?:dollars?|euros?|pounds?|lira|tl|usd|eur|try)\b", re.IGNORECASE)


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2:
            value = value * 2 - 9 if value > 4 else value * 2
        total += value
    return total % 10 == 0


def _number(match: re.Match[str]) -> str:
    text = match.group(0)
    digits = re.sub(r"\D", "", text)
    if _CURRENCY_AFTER.match(match.string[match.end() :]):
        return text
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):  # an ISO date
        return text
    if 13 <= len(digits) <= 19 and _luhn(digits):
        return "[card number]"
    if 9 <= len(digits) <= 15:
        return "[phone number]"
    return text


def redact(text: str) -> str:
    """Return ``text`` with personal data and secrets replaced by placeholders."""
    text = _SECRET.sub("[secret]", text)
    text = _EMAIL.sub("[email]", text)
    text = _IBAN.sub("[iban]", text)
    text = _PASSWORD.sub(lambda m: f"{m.group(1)}{m.group(2)}[secret]", text)
    return _DIGITS.sub(_number, text)


def redact_segment(segment: Segment) -> Segment:
    """Return ``segment`` with its text and every word redacted.

    Word timings are kept, so a redacted segment still lines up with the
    recording; a word that contained a secret becomes its placeholder.
    """
    text = redact(segment.text)
    if text == segment.text:
        return segment
    words = tuple(replace(word, text=redact(word.text)) for word in segment.words)
    return replace(segment, text=text, words=words)


def disk_encryption_active() -> bool | None:
    """Whether macOS FileVault is on; ``None`` when it cannot be told (other systems)."""
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            ["/usr/bin/fdesetup", "isactive"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() == "true"


def storage_settings(settings: "Settings") -> "Settings":
    """Return ``settings`` with storing turned off when it requires an encrypted disk that is not.

    With ``require_disk_encryption``, notes, memory, recordings and voices are
    only kept when FileVault is confirmed on; otherwise the live transcript
    still runs and nothing is written to disk.
    """
    if not settings.require_disk_encryption or disk_encryption_active() is True:
        return settings
    logger.error(
        "Disk encryption is required but FileVault is not confirmed on: nothing will be stored "
        "(no notes, memory, recordings or voices). Turn it on in System Settings > "
        "Privacy & Security > FileVault."
    )
    return replace(settings, scope=None, notes_dir=None, record_audio=False, remember_voices=False)


def warn_if_disk_unencrypted() -> None:
    """Log a warning when transcripts would be stored on an unencrypted disk."""
    if disk_encryption_active() is False:
        logger.warning(
            "FileVault is off: stored transcripts and notes are not encrypted on disk. "
            "Turn it on in System Settings > Privacy & Security > FileVault."
        )
