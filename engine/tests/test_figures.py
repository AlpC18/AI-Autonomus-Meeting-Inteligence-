# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Figure extraction: amounts, percentages and counted units are normalised."""

import pytest

from recall.factcheck.figures import extract_figures, mask_figures


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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("otuz bin dolarlık bütçe", {("money", 30_000.0)}),
        ("bütçe 35 bin dolara çıktı", {("money", 35_000.0)}),
        ("üç günlük iş", {("count:gün", 3.0)}),
        ("beş kişilik ekip", {("count:kişi", 5.0)}),
        ("on günde biter", {("count:gün", 10.0)}),
        ("5 aylık plan", {("count:ay", 5.0)}),
        ("40 müşteriye ulaştık", {("count:müşteri", 40.0)}),
    ],
)
def test_turkish_units_with_suffixes_are_understood(text: str, expected: set) -> None:
    assert figures(text) == expected


@pytest.mark.parametrize("text", ["2 ayrıca", "3 günah", "5 dolaşım"])
def test_words_that_only_start_like_a_unit_are_not_units(text: str) -> None:
    assert figures(text) == set()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Das Budget wurde auf fünfunddreißigtausend Euro gesenkt", {("money", 35_000.0)}),
        ("Wir brauchen zwei Entwickler für drei Wochen", {("count:developer", 2.0), ("count:week", 3.0)}),
        ("dreihundertzwölf Kunden", {("count:customer", 312.0)}),
        ("zwanzig Prozent Rabatt", {("percent", 20.0)}),
        ("ein Budget von 35 Millionen Euro", {("money", 35_000_000.0)}),
        ("Start am 14. Oktober", {("date", 1014.0)}),
        ("bis zum 3. März", {("date", 303.0)}),
        ("das dauert sechzehn Tage", {("count:day", 16.0)}),
    ],
)
def test_german_figures_are_understood(text: str, expected: set) -> None:
    assert figures(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("il budget è di trentacinquemila euro", {("money", 35_000.0)}),
        ("ci vogliono ventuno giorni", {("count:day", 21.0)}),
        ("due sviluppatori per tre settimane", {("count:developer", 2.0), ("count:week", 3.0)}),
        ("centoventi utenti", {("count:user", 120.0)}),
        ("uno sconto del trenta per cento", {("percent", 30.0)}),
        ("costa 35mila euro", {("money", 35_000.0)}),
        ("il lancio è il 14 ottobre", {("date", 1014.0)}),
        ("Il lancio è il quattordici ottobre", {("date", 1014.0)}),
        ("2 milioni di euro", {("money", 2_000_000.0)}),
    ],
)
def test_italian_figures_are_understood(text: str, expected: set) -> None:
    assert figures(text) == expected


@pytest.mark.parametrize("text", ["ein Tag wie jeder andere", "una settimana tranquilla", "sei bravo", "Tag 3"])
def test_german_and_italian_articles_and_words_are_not_figures(text: str) -> None:
    assert figures(text) == set()


def test_the_same_unit_compares_across_languages() -> None:
    assert figures("drei Wochen") == figures("tre settimane") == figures("three weeks") == {("count:week", 3.0)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # As large-v3-turbo writes Albanian speech: digits with Albanian units.
        ("Bugjeti u ul në 35.000 euro.", {("money", 35_000.0)}),
        ("Na duhen 2 zhvillues për 3 javë.", {("count:developer", 2.0), ("count:week", 3.0)}),
        ("Klienti kërkon një zbritje për 20%.", {("percent", 20.0)}),
        ("çmimi është 5000 lekë", {("money", 5000.0)}),
        ("buxheti 2 milionë euro", {("money", 2_000_000.0)}),
        ("35 mijë euro", {("money", 35_000.0)}),
        # Spoken numbers.
        ("buxheti u ul në tridhjetë e pesë mijë euro", {("money", 35_000.0)}),
        ("na duhen dy zhvillues për tre javë", {("count:developer", 2.0), ("count:week", 3.0)}),
        ("njëzet për qind zbritje", {("percent", 20.0)}),
        ("dyqind e pesëdhjetë përdorues", {("count:user", 250.0)}),
        ("katërmbëdhjetë ditë", {("count:day", 14.0)}),
        ("lansimi është më 14 tetor", {("date", 1014.0)}),
        ("afati: 3 Mars", {("date", 303.0)}),
    ],
)
def test_albanian_figures_are_understood(text: str, expected: set) -> None:
    assert figures(text) == expected


@pytest.mark.parametrize("text", ["një javë e qetë", "e premte", "tetori ishte i ngrohtë"])
def test_albanian_articles_and_words_are_not_figures(text: str) -> None:
    assert figures(text) == set()


def test_albanian_units_compare_with_the_other_languages() -> None:
    assert figures("tre javë") == figures("drei Wochen") == figures("three weeks") == {("count:week", 3.0)}
