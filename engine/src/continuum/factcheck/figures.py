# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Finds the amounts, percentages and counts mentioned in a sentence."""

import re
from dataclasses import dataclass

_MULTIPLIERS = {
    "k": 1e3, "thousand": 1e3, "bin": 1e3,
    "m": 1e6, "mn": 1e6, "million": 1e6, "milyon": 1e6,
    "bn": 1e9, "billion": 1e9, "milyar": 1e9,
}  # fmt: skip
_CURRENCY_WORDS = frozenset(
    {"dollar", "usd", "euro", "eur", "pound", "gbp", "lira", "tl", "dolar", "avro"}
)
_UNITS = frozenset(
    {
        "day", "week", "month", "year", "hour", "minute", "sprint", "engineer",
        "developer", "people", "person", "user", "customer", "ticket", "point",
        "seat", "license",
        "gün", "hafta", "ay", "yıl", "saat", "dakika", "kişi", "mühendis",
        "kullanıcı", "müşteri",
    }
)  # fmt: skip

_NUMBER = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_FIGURE = re.compile(
    rf"""
    (?<!\w)
    (?P<percent_before>yüzde\s+|%\s?)?
    (?P<currency>[$€£₺]\s?)?
    (?P<number>{_NUMBER})
    (?:\s?(?P<multiplier>{"|".join(sorted(_MULTIPLIERS, key=len, reverse=True))})\b)?
    (?:\s?(?P<percent_after>%|percent\b))?
    (?:\s(?P<word>[^\W\d_]+))?
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class Figure:
    """A quantity found in text.

    ``kind`` says what is measured (``"money"``, ``"percent"`` or
    ``"count:<unit>"`` such as ``"count:week"``), ``value`` is the normalised
    number, and ``text`` is the original wording for display. Only figures of
    the same kind are comparable.
    """

    kind: str
    value: float
    text: str


def _parse_number(raw: str) -> float:
    """Read ``35,000``, ``35.000``, ``1,234.56`` or ``4,5`` as a number.

    A separator followed by exactly three digits is a thousands separator;
    the last separator followed by any other count of digits is the decimal
    point.
    """
    last = max(raw.rfind("."), raw.rfind(","))
    if last == -1:
        return float(raw)
    whole, fraction = raw[:last], raw[last + 1 :]
    whole = whole.replace(".", "").replace(",", "")
    if len(fraction) == 3:
        return float(whole + fraction)
    return float(f"{whole}.{fraction}")


def _singular(word: str) -> str:
    lowered = word.lower()
    if lowered.endswith("s") and lowered[:-1] in _UNITS | _CURRENCY_WORDS:
        return lowered[:-1]
    return lowered


def mask_figures(text: str) -> str:
    """Return ``text`` with its figures removed and whitespace tidied.

    What is left describes the topic ("the budget was") without the value, so
    two statements about the same thing compare as similar even when their
    numbers differ.
    """
    for figure in extract_figures(text):
        text = text.replace(figure.text, " ")
    return " ".join(text.split())


def extract_figures(text: str) -> list[Figure]:
    """Return every money amount, percentage and counted unit in ``text``.

    Understands thousands separators, ``k``/``million``-style multipliers,
    currency symbols and words, and a fixed list of English and Turkish units.
    Bare numbers with no recognised unit (years, room numbers, versions) are
    ignored on purpose: they are not comparable facts.
    """
    # ponytail: digits only. Spelled-out numbers ("thirty five thousand") and
    # dates are not recognised; Whisper writes most amounts as digits. Add a
    # words-to-number pass if spoken figures are being missed.
    figures = []
    for match in _FIGURE.finditer(text):
        value = _parse_number(match["number"])
        if match["multiplier"]:
            value *= _MULTIPLIERS[match["multiplier"].lower()]
        word = _singular(match["word"]) if match["word"] else ""

        end = match.end("multiplier") if match["multiplier"] else match.end("number")
        if match["percent_before"] or match["percent_after"]:
            kind = "percent"
            end = match.end("percent_after") if match["percent_after"] else end
        elif match["currency"] or word in _CURRENCY_WORDS:
            kind = "money"
            end = match.end("word") if word in _CURRENCY_WORDS else end
        elif word in _UNITS:
            kind = f"count:{word}"
            end = match.end("word")
        else:
            continue
        figures.append(Figure(kind, value, text[match.start() : end]))
    return figures
