# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Figure extraction: amounts, percentages and counted units are normalised."""

import pytest

from continuum.factcheck.figures import extract_figures


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
