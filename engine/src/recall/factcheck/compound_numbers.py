# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""German, Italian and Albanian number words: "fünfunddreißigtausend", "trentacinquemila", "katërmbëdhjetë".

These languages join the parts of a number into a single word, so they are
read by splitting the word into known parts rather than word by word.
Albanian then joins words with "e" ("tridhjetë e pesë"), which
:mod:`recall.factcheck.figures` handles like "and".
"""

_DE_ONES = {
    "eins": 1, "ein": 1, "eine": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12,
    "dreizehn": 13, "vierzehn": 14, "fünfzehn": 15, "sechzehn": 16, "siebzehn": 17,
    "achtzehn": 18, "neunzehn": 19,
}  # fmt: skip
_DE_TENS = {
    "zwanzig": 20, "dreißig": 30, "vierzig": 40, "fünfzig": 50,
    "sechzig": 60, "siebzig": 70, "achtzig": 80, "neunzig": 90,
}  # fmt: skip

_IT_ONES = {
    "uno": 1, "una": 1, "un": 1, "due": 2, "tre": 3, "tré": 3, "quattro": 4, "cinque": 5,
    "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "undici": 11, "dodici": 12,
    "tredici": 13, "quattordici": 14, "quindici": 15, "sedici": 16, "diciassette": 17,
    "diciotto": 18, "diciannove": 19,
}  # fmt: skip
_IT_TENS = {
    "venti": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50,
    "sessanta": 60, "settanta": 70, "ottanta": 80, "novanta": 90,
}  # fmt: skip
# Before "uno" and "otto" the tens lose their last vowel: "ventuno", "trentotto".
_IT_TENS_ELIDED = {word[:-1]: value for word, value in _IT_TENS.items()}

_SQ_ONES = {
    "një": 1, "dy": 2, "tre": 3, "tri": 3, "katër": 4, "pesë": 5,
    "gjashtë": 6, "shtatë": 7, "tetë": 8, "nëntë": 9,
}  # fmt: skip
_SQ_TENS = {"njëzet": 20, "dyzet": 40}
"""The tens not made as "<n>dhjetë" ("tridhjetë" is thirty)."""

ARTICLES = frozenset({"ein", "eine", "un", "una", "uno", "një"})
"""Words for "one" that are usually just "a": alone they are not a number."""


def _split(word: str, parts: dict[str, int | str]) -> list[int | str] | None:
    """``word`` as a sequence of known parts (longest first), or ``None``."""
    found: list[int | str] = []
    position = 0
    while position < len(word):
        for end in range(len(word), position, -1):
            if word[position:end] in parts:
                found.append(parts[word[position:end]])
                position = end
                break
        else:
            return None
    return found


def _german(word: str) -> float | None:
    """Units come before the tens: "fünfunddreißig" is five-and-thirty."""
    parts = _split(word, {**_DE_ONES, **_DE_TENS, "und": "und", "hundert": "hundert", "tausend": "tausend"})
    if not parts or parts == ["und"]:
        return None
    total = current = ones = 0
    for part in parts:
        if part == "hundert":
            current = (current + ones or 1) * 100
            ones = 0
        elif part == "tausend":
            total += (current + ones or 1) * 1000
            current = ones = 0
        elif part == "und":
            continue
        elif part >= 20:
            current += part + ones
            ones = 0
        else:
            ones = part
    return float(total + current + ones)


def _italian(word: str) -> float | None:
    """Tens come first: "trentacinque" is thirty-five; "mila" multiplies by a thousand."""
    parts = _split(
        word, {**_IT_ONES, **_IT_TENS, **_IT_TENS_ELIDED, "cento": "cento", "mila": "mila", "mille": "mille"}
    )
    if not parts:
        return None
    total = current = 0
    for part in parts:
        if part == "cento":
            current = (current or 1) * 100
        elif part == "mila":
            total += (current or 1) * 1000
            current = 0
        elif part == "mille":
            total += 1000
        else:
            current += part
    return float(total + current)


def _albanian(word: str) -> float | None:
    """One word: "pesë", "dhjetë", "katërmbëdhjetë" (4 + 10), "pesëdhjetë" (5 x 10), "dyqind" (2 x 100)."""
    parts = _split(word, {**_SQ_ONES, **_SQ_TENS, "mbëdhjetë": "teen", "dhjetë": "ten", "qind": "hundred"})
    match parts:
        case [int() as value]:
            return float(value)
        case ["ten"]:
            return 10.0
        case ["hundred"]:
            return 100.0
        case [int() as ones, "teen"] if ones < 10:
            return float(10 + ones)
        case [int() as ones, "ten"] if ones < 10:
            return float(10 * ones)
        case [int() as ones, "hundred"] if ones < 10:
            return float(100 * ones)
    return None


def compound_value(word: str) -> float | None:
    """The value of a German, Italian or Albanian number word, or ``None`` if it is not one."""
    lowered = word.lower()
    for read in (_german, _italian, _albanian):
        value = read(lowered)
        if value is not None:
            return value
    return None


if __name__ == "__main__":
    for text, expected in [
        ("fünfunddreißigtausend", 35_000), ("dreihundertzwölf", 312), ("einundzwanzig", 21),
        ("trentacinquemila", 35_000), ("ventuno", 21), ("trentotto", 38), ("centoventi", 120),
        ("duemila", 2000), ("mille", 1000), ("budget", None), ("und", None),
        ("pesë", 5), ("katërmbëdhjetë", 14), ("tridhjetë", 30), ("dyzet", 40), ("dyqind", 200),
        ("njëqind", 100), ("dhjetë", 10), ("tetor", None), ("dhjetor", None),
    ]:  # fmt: skip
        assert compound_value(text) == expected, (text, compound_value(text))
    print("ok")
