# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""The language of everything Continuum writes: note headings, hints and AI replies.

Set once at start from ``CONTINUUM_LANGUAGE`` (``en`` or ``tr``). What people
say is transcribed in whatever language they speak, whatever this is.
"""

import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from continuum.llm import Llm

LANGUAGES = ("en", "tr")
NAMES = {"en": "English", "tr": "Turkish"}

_TR = {
    "Meeting": "Toplantı",
    "Summary": "Özet",
    "Decisions": "Kararlar",
    "Action items": "Yapılacaklar",
    "due {date}": "son tarih {date}",
    "Talk time": "Konuşma süreleri",
    "Speaker": "Konuşan",
    "Share": "Pay",
    "Longest turn": "En uzun konuşma",
    "Interruptions": "Söz kesme",
    "Commitments": "Taahhütler",
    "Hesitations": "Tereddütler",
    "{speaker} promised a date: {day}": "{speaker} bir tarih verdi: {day}",
    "{speaker} has {open} open {source} issues, {due} due by then{sprint}.":
        "{speaker} kişisinin {open} açık {source} işi var, {due} tanesi o tarihe kadar bitmeli{sprint}.",
    ", {count} in the current sprint": ", {count} tanesi bu sprintte",
    "Recording": "Kayıt",
    "Follow-up: {title}": "Toplantı sonrası: {title}",
    "Follow-up from our meeting": "Toplantımızın ardından",
    "Hi all,": "Herkese merhaba,",
    "Thanks for joining. Here is a short recap.": "Katıldığınız için teşekkürler. Kısa bir özet:",
    "Next steps": "Sonraki adımlar",
    "Let me know if I missed anything.": "Atladığım bir şey varsa lütfen haber verin.",
    "Best regards": "Saygılarımla",
}
_TABLES = {"tr": _TR}
_current: str | None = None


def use(language: str) -> None:
    """Write in ``language`` from now on.

    Raises:
        ValueError: if it is not one of :data:`LANGUAGES`.
    """
    global _current
    if language not in LANGUAGES:
        raise ValueError(f"language must be one of {LANGUAGES}, got {language!r}")
    _current = language


def current() -> str:
    """The language set with :func:`use`, else ``CONTINUUM_LANGUAGE``, else English."""
    if _current is not None:
        return _current
    chosen = os.environ.get("CONTINUUM_LANGUAGE", "").strip().lower()
    return chosen if chosen in LANGUAGES else "en"


def t(text: str, **values: object) -> str:
    """``text`` in the current language (English when there is no translation), filled with ``values``."""
    return _TABLES.get(current(), {}).get(text, text).format(**values)


def headings(english: str) -> tuple[str, ...]:
    """``english`` and every translation of it, for reading notes written in any language."""
    return (english, *(table[english] for table in _TABLES.values() if english in table))


def heading_pattern(english: str, level: str = "##") -> re.Pattern[str]:
    """A pattern matching the ``level`` heading ``english`` in any language."""
    return re.compile(rf"^{level} (?:{'|'.join(map(re.escape, headings(english)))})$", re.MULTILINE)


class InLanguage:
    """An :class:`~continuum.llm.Llm` told to write its free text in the current language."""

    def __init__(self, llm: "Llm") -> None:
        self._llm = llm

    @property
    def inner(self) -> "Llm":
        """The provider's client."""
        return self._llm

    def complete(self, system: str, user: str) -> str:
        language = current()
        if language == "en":
            return self._llm.complete(system, user)
        rule = (
            f"\n\nWrite every sentence meant for people (summaries, answers, reasons) in {NAMES[language]}. "
            "Keep JSON keys, dates and quoted transcript text unchanged."
        )
        return self._llm.complete(system + rule, user)
