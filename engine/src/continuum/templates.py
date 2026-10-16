# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Meeting templates: the extra summary sections a kind of meeting needs.

A standup is summarised as what was done, what is next and what blocks
people; a sales call as the customer's needs, objections and budget. The
kind comes from ``CONTINUUM_MEETING_TEMPLATE`` or, with ``auto``, from the
calendar title ("Daily standup", "1:1 with Ana", "Interview: ...").
"""

import os
import re

TEMPLATES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "standup": (
        ("done", "Done", "what each person finished"),
        ("next", "Next", "what each person will do next"),
        ("blockers", "Blockers", "what blocks someone, and who can help"),
    ),
    "one_on_one": (
        ("feedback", "Feedback", "feedback given in either direction"),
        ("concerns", "Concerns", "worries or problems raised"),
        ("growth", "Growth", "goals, learning and career topics"),
    ),
    "sales": (
        ("needs", "Customer needs", "the problems and requirements the customer described"),
        ("objections", "Objections", "doubts or objections the customer raised"),
        ("budget", "Budget and timeline", "budget, pricing and timing mentioned"),
        ("competitors", "Competitors", "other vendors or alternatives mentioned"),
    ),
    "interview": (
        ("strengths", "Strengths", "the candidate's strengths, with evidence"),
        ("concerns", "Concerns", "gaps or concerns, with evidence"),
        ("recommendation", "Recommendation", "the interviewers' leaning, if stated; never invent one"),
    ),
    "retro": (
        ("went_well", "What went well", "what the team wants to keep"),
        ("to_improve", "What to improve", "what went badly or should change"),
    ),
}
"""Each template's sections: ``(JSON key, heading, what belongs in it)``."""

CHOICES = ("auto", "general", *TEMPLATES)
"""Values of ``CONTINUUM_MEETING_TEMPLATE``."""

_DETECT = (
    ("standup", re.compile(r"\b(?:stand-?up|daily|scrum|günlük toplantı)\b", re.IGNORECASE)),
    ("one_on_one", re.compile(r"(?:\b1[:-]1\b|\bone[- ]on[- ]one\b|\bbirebir\b)", re.IGNORECASE)),
    ("interview", re.compile(r"\b(?:interview|mülakat)\b", re.IGNORECASE)),
    ("retro", re.compile(r"\bretro(?:spective)?\b", re.IGNORECASE)),
    ("sales", re.compile(r"\b(?:demo|sales|discovery call|prospect|satış)\b", re.IGNORECASE)),
)


def for_meeting(title: str | None) -> str | None:
    """The template for a meeting titled ``title``, following ``CONTINUUM_MEETING_TEMPLATE`` (default ``auto``)."""
    return choose(os.environ.get("CONTINUUM_MEETING_TEMPLATE", "").strip().lower() or "auto", title)


def choose(setting: str, title: str | None) -> str | None:
    """The template to use: ``setting``, or with ``auto`` the one ``title`` suggests; ``None`` for a general meeting."""
    if setting in TEMPLATES:
        return setting
    if setting == "auto" and title:
        return next((name for name, pattern in _DETECT if pattern.search(title)), None)
    return None


def prompt(template: str) -> str:
    """What to add to the summary prompt for ``template``."""
    keys = ", ".join(f'"{key}": ["..."]' for key, _heading, _what in TEMPLATES[template])
    lines = "\n".join(f'- "{key}": {what}' for key, _heading, what in TEMPLATES[template])
    return (
        f"\n\nThis was a {template.replace('_', ' ')} meeting. Also include "
        f'"sections": {{{keys}}} with short points for:\n{lines}\n'
        "Use empty lists where the meeting said nothing about a section."
    )
