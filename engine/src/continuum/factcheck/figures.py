# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Finds the amounts, percentages, counts and dates mentioned in a sentence."""

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


_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen",
]  # fmt: skip
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_TR_ONES = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_TR_TENS = ["on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
_WORD_VALUES = (
    {word: float(value) for value, word in enumerate(_ONES)}
    | {word: float(10 * tens) for tens, word in enumerate(_TENS, start=2)}
    | {word: float(value) for value, word in enumerate(_TR_ONES)}
    | {word: float(10 * tens) for tens, word in enumerate(_TR_TENS, start=1)}
)
_HUNDREDS = frozenset({"hundred", "yüz"})
_SCALES = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "bin": 1e3, "milyon": 1e6, "milyar": 1e9}
_NUMBER_WORDS = frozenset(_WORD_VALUES) | _HUNDREDS | frozenset(_SCALES)
# Turkish number words that are also ordinary words ("bir" = "a", "on" in English,
# "yüz" = "face"): alone they count only before a Turkish unit or currency.
_AMBIGUOUS = frozenset({"bir", "on", "yüz"})
_TR_UNITS = frozenset({"gün", "hafta", "ay", "yıl", "saat", "dakika", "kişi", "mühendis", "kullanıcı", "müşteri", "dolar", "avro", "lira", "tl"})
_WORD = re.compile(r"[^\W\d_]+")
_JOINER = re.compile(r"[\s-]+")

_MONTHS = {
    name: number
    for names in (
        "January February March April May June July August September October November December",
        "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık",
    )
    for number, name in enumerate(names.split(), start=1)
}
_MONTH = "|".join(_MONTHS)
_DAY = r"(?P<{}>\d{{1,2}})(?:st|nd|rd|th)?"
# Capitalised month names only, so "you may 5" is not a date.
_DATE = re.compile(
    rf"(?<!\w)(?:(?P<month>{_MONTH})\s+{_DAY.format('day')}"
    rf"|{_DAY.format('day_first')}\s+(?:of\s+)?(?P<month_after>{_MONTH}))(?!\w)"
)

Replacement = tuple[int, int, int, int]
"""Span of a rewritten number: start and end in the new text, then in the original."""


@dataclass(frozen=True, slots=True)
class Figure:
    """A quantity found in text.

    ``kind`` says what is measured (``"money"``, ``"percent"``, ``"date"``
    or ``"count:<unit>"`` such as ``"count:week"``), ``value`` is the normalised
    number (a date is ``month * 100 + day``), and ``text`` is the original wording for display. Only figures of
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


def _words_value(words: list[str]) -> float:
    """``["thirty", "five", "thousand"]`` → 35000; ``["one", "point", "five"]`` → 1.5."""
    total = current = 0.0
    fraction: str | None = None
    for word in words:
        if word == "point":
            fraction = ""
            continue
        if fraction is not None and _WORD_VALUES.get(word, 10) < 10:
            fraction += str(int(_WORD_VALUES[word]))
            continue
        if fraction:
            current += float(f"0.{fraction}")
        fraction = None
        if word in _WORD_VALUES:
            current += _WORD_VALUES[word]
        elif word in _HUNDREDS:
            current = (current or 1) * 100
        elif word in _SCALES:
            total += (current or 1) * _SCALES[word]
            current = 0.0
    if fraction:
        current += float(f"0.{fraction}")
    return total + current


def _digits(value: float) -> str:
    """Write ``value`` so that :func:`_parse_number` reads it back unchanged."""
    if value.is_integer():
        return str(int(value))
    text = f"{value:.6f}".rstrip("0")
    # Exactly three decimals would read as a thousands separator.
    return text + "0" if len(text.split(".")[1]) == 3 else text


def _number_runs(text: str) -> list[tuple[int, int, float]]:
    """Spans of spelled-out English and Turkish numbers in ``text`` and their values."""
    tokens = list(_WORD.finditer(text))
    runs = []
    i = 0
    while i < len(tokens):
        words: list[str] = []
        j = i
        while j < len(tokens):
            word = tokens[j].group().lower()
            following = tokens[j + 1].group().lower() if j + 1 < len(tokens) else ""
            joined = j == i or _JOINER.fullmatch(text[tokens[j - 1].end() : tokens[j].start()])
            if not joined:
                break
            if word in _NUMBER_WORDS or word == "a" and not words and following in {"hundred", *_SCALES} or word in {"and", "point"} and words and following in _WORD_VALUES:
                words.append(word)
            else:
                break
            j += 1
        # A bare scale word ("35 thousand") is left to the digit multipliers.
        counted = words and (words[0] == "a" or any(word in _WORD_VALUES for word in words))
        if len(words) == 1 and words[0] in _AMBIGUOUS:
            after = tokens[j].group().lower() if j < len(tokens) else ""
            counted = words[0] != "bir" and after in _TR_UNITS
        if counted:
            runs.append((tokens[i].start(), tokens[j - 1].end(), _words_value(words)))
            i = j
        else:
            i += 1
    return runs


def _with_digits(text: str) -> tuple[str, list[Replacement]]:
    """``text`` with spelled-out numbers written as digits, and where each one was."""
    parts: list[str] = []
    replacements: list[Replacement] = []
    written = cursor = 0
    for start, end, value in _number_runs(text):
        parts.append(text[cursor:start])
        written += start - cursor
        digits = _digits(value)
        replacements.append((written, written + len(digits), start, end))
        parts.append(digits)
        written += len(digits)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), replacements


def _original(position: int, replacements: list[Replacement], end: bool) -> int:
    """Map a position in the rewritten text back to the original text."""
    shift = 0
    for new_start, new_end, old_start, old_end in replacements:
        if (new_start < position <= new_end) if end else (new_start <= position < new_end):
            return old_end if end else old_start
        if position >= new_end:
            shift += (old_end - old_start) - (new_end - new_start)
    return position + shift


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
    """Return every money amount, percentage, counted unit and date in ``text``.

    Understands thousands separators, ``k``/``million``-style multipliers,
    spelled-out English numbers ("thirty-five thousand"), currency symbols and
    words, a fixed list of English and Turkish units, and dates written with a
    month name ("March 3rd", "14 October", "5 Mart"). Bare numbers with no
    recognised unit (years, room numbers, versions) are ignored on purpose:
    they are not comparable facts. ``Figure.text`` is the original wording.
    """
    original = text
    text, replacements = _with_digits(original)

    def figure(kind: str, value: float, start: int, end: int) -> Figure:
        return Figure(
            kind,
            value,
            original[_original(start, replacements, False) : _original(end, replacements, True)],
        )

    figures = []
    for match in _DATE.finditer(text):
        day = int(match["day"] or match["day_first"])
        month = _MONTHS[match["month"] or match["month_after"]]
        if 1 <= day <= 31:
            figures.append(figure("date", float(month * 100 + day), match.start(), match.end()))
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
        figures.append(figure(kind, value, match.start(), end))
    return figures
