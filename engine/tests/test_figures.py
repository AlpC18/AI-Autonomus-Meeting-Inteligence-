# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Figure extraction: amounts, percentages and counted units are normalised."""

import pytest

from continuum.factcheck.figures import extract_figures, mask_figures


def figures(text: str) -> set[tuple[str, float]]:
    return {(figure.kind, figure.value) for figure in extract_figures(text)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("the budget was revised down to $35,000.", {("money", 35_000.0)}),
        ("we agreed on $35k", {("money", 35_000.0)}),
        ("it costs 35 thousand dollars", {("money", 35_000.0)}),
        ("around 1.5 million euros", {("money", 1_500_000.0)}),
        ("€2.5m in revenue", {("money", 2_500_000.0)}),
        ("bütçe 35.000 TL olarak belirlendi", {("money", 35_000.0)}),
        ("bütçe 35 bin lira", {("money", 35_000.0)}),
        ("churn is 4.5%", {("percent", 4.5)}),
        ("a 20 percent discount", {("percent", 20.0)}),
        ("yüzde 20 indirim", {("percent", 20.0)}),
        ("the deadline is in 3 weeks", {("count:week", 3.0)}),
        ("teslim 2 hafta sonra", {("count:hafta", 2.0)}),
        ("we need 4 engineers", {("count:engineer", 4.0)}),
    ],
)
def test_figures_are_extracted_and_normalised(text: str, expected: set) -> None:
    assert figures(text) == expected


@pytest.mark.parametrize(
    "text",
    ["no numbers here", "see you in 2026", "room 12 is free", "version 3 of the plan"],
)
def test_bare_numbers_without_a_known_unit_are_ignored(text: str) -> None:
    assert figures(text) == set()


def test_several_figures_in_one_sentence() -> None:
    assert figures("$50k over 6 months with 10% contingency") == {
        ("money", 50_000.0),
        ("count:month", 6.0),
        ("percent", 10.0),
    }


def test_original_wording_is_kept_for_display() -> None:
    (figure,) = extract_figures("revised down to $35,000.")

    assert figure.text == "$35,000"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("it costs thirty-five thousand dollars", {("money", 35_000.0)}),
        ("a hundred and twenty users signed up", {("count:user", 120.0)}),
        ("we need two engineers for three weeks", {("count:engineer", 2.0), ("count:week", 3.0)}),
        ("about five percent churn", {("percent", 5.0)}),
        ("one point five million euros", {("money", 1_500_000.0)}),
        ("twelve million dollars", {("money", 12_000_000.0)}),
    ],
)
def test_spelled_out_numbers_are_understood(text: str, expected: set) -> None:
    assert figures(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("the launch is on March 3rd", {("date", 303.0)}),
        ("we ship on 14 October", {("date", 1014.0)}),
        ("teslim 5 Mart", {("date", 305.0)}),
        ("due the 21st of June", {("date", 621.0)}),
    ],
)
def test_dates_are_comparable(text: str, expected: set) -> None:
    assert figures(text) == expected


def test_spelled_out_wording_is_kept_for_display_and_masking() -> None:
    (figure,) = extract_figures("revised to thirty-five thousand dollars.")
    assert figure.text == "thirty-five thousand dollars"
    assert mask_figures("revised to thirty-five thousand dollars.") == "revised to ."


@pytest.mark.parametrize("text", ["the one we discussed", "you may 5", "March on", "on 40 March"])
def test_words_and_months_alone_are_not_figures(text: str) -> None:
    assert figures(text) == set()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("bütçe otuz beş bin dolar", {("money", 35_000.0)}),
        ("iki yüz kullanıcı kaydoldu", {("count:kullanıcı", 200.0)}),
        ("on gün sürer", {("count:gün", 10.0)}),
        ("yüzde yirmi beş indirim", {("percent", 25.0)}),
        ("üç mühendis iki hafta", {("count:mühendis", 3.0), ("count:hafta", 2.0)}),
        ("yüz kişi geldi", {("count:kişi", 100.0)}),
    ],
)
def test_spoken_turkish_numbers_are_understood(text: str, expected: set) -> None:
    assert figures(text) == expected


@pytest.mark.parametrize(
    "text",
    ["bir müşteri aradı", "we agreed on point two", "on day one", "yüz yüze görüştük"],
)
def test_turkish_words_that_double_as_ordinary_words_are_not_figures(text: str) -> None:
    assert figures(text) == set()
