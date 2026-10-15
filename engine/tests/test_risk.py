# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Risk tracking: promised dates against workload, and moments of hesitation."""

from datetime import date

import httpx
import pytest

from continuum.actions.jira import JiraAccess
from continuum.context.risk import RiskTracker, Workload, due_date
from continuum.context.workload import JiraWorkload
from continuum.transcript import Segment

WEDNESDAY = date(2026, 10, 14)


def said(text: str, speaker: str = "Ana", start: float = 65.0) -> Segment:
    return Segment("system", start, start + 2, text, (), speaker)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I'll have it done by Friday", date(2026, 10, 16)),
        ("we can ship it tomorrow", date(2026, 10, 15)),
        ("ready by end of day", WEDNESDAY),
        ("done by the end of the week", date(2026, 10, 16)),
        ("sometime next week", date(2026, 10, 23)),
        ("before end of month", date(2026, 10, 31)),
        ("by Wednesday", date(2026, 10, 21)),
        ("by 2026-11-02", date(2026, 11, 2)),
        ("no date here", None),
    ],
)
def test_due_dates_are_read_relative_to_today(text: str, expected: date | None) -> None:
    assert due_date(text, WEDNESDAY) == expected


def test_a_promise_against_a_full_plate_gets_a_hint() -> None:
    asked: list[tuple[str, date]] = []

    def workload(speaker: str, due: date) -> Workload:
        asked.append((speaker, due))
        return Workload(open=12, due_by=4, source="Jira")

    tracker = RiskTracker(lambda: WEDNESDAY, workload)
    (hint,) = tracker.watch(said("Sure, I'll have the export done by Friday"))

    assert asked == [("Ana", date(2026, 10, 16))]
    assert hint["kind"] == "commitment"
    assert "Ana" in hint["title"] and "12 open Jira issues, 4 due" in hint["body"]


def test_a_promise_with_room_to_spare_or_no_date_gets_no_hint() -> None:
    tracker = RiskTracker(lambda: WEDNESDAY, lambda speaker, due: Workload(open=2, due_by=0, source="Jira"))
    assert tracker.watch(said("I'll have it done by Friday")) == []
    assert tracker.watch(said("I'll look into it")) == []
    assert tracker.watch(said("Friday is a holiday")) == []  # a date but no promise


def test_hesitations_and_commitments_are_reported_when_the_meeting_ends() -> None:
    tracker = RiskTracker(lambda: WEDNESDAY, None)
    tracker.watch(said("I'm not sure we can do that", "Mark", 125.0))
    tracker.watch(said("I will send the report by Friday"))
    tracker.watch(said("Sounds good"))

    report = tracker.finish()

    assert report is not None
    assert "## Commitments" in report and "**Ana:** I will send the report by Friday (due 2026-10-16)" in report
    assert "## Hesitations" in report and "`00:02:05` **Mark:** I'm not sure we can do that" in report
    assert tracker.finish() is None  # the next meeting starts clean


def test_jira_workload_counts_open_and_due_issues_of_the_named_person() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/rest/api/3/user/search":
            return httpx.Response(200, json=[{"accountId": "abc123", "active": True, "displayName": "Ana"}])
        jql = request.read().decode()
        return httpx.Response(200, json={"count": 4 if "duedate" in jql else 12})

    access = JiraAccess("https://acme.atlassian.net", "me@acme.io", "token")
    workload = JiraWorkload(access, httpx.Client(transport=httpx.MockTransport(handler)))

    assert workload("Ana", date(2026, 10, 16)) == Workload(open=12, due_by=4, source="Jira")
    assert 'assignee = \\"abc123\\"' in seen[1].read().decode()
    assert workload("me", date(2026, 10, 16)) is not None
    assert "currentUser()" in seen[-1].read().decode()
    assert workload("Speaker 2", date(2026, 10, 16)) is None  # nobody to look up


def test_jira_workload_gives_up_quietly_on_unknown_people_and_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/user/search":
            return httpx.Response(200, json=[])
        return httpx.Response(500)

    access = JiraAccess("https://acme.atlassian.net", "me@acme.io", "token")
    workload = JiraWorkload(access, httpx.Client(transport=httpx.MockTransport(handler)))
    assert workload("Nobody", date(2026, 10, 16)) is None
    assert workload("me", date(2026, 10, 16)) is None
