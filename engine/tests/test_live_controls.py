# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Live notes and speaker names sent by the desktop app."""

import asyncio
import json
from pathlib import Path

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from recall.live_controls import (
    NOTE_SPEAKER,
    Note,
    Rename,
    SpeakerNames,
    clean_name,
    note_segment,
    parse,
)
from recall.notes import markdown_lines
from recall.transcript import Segment, Word
from recall.transport.server import MAX_CLIENT_MESSAGE, TranscriptServer

ORIGIN = "http://localhost:1420"


def segment(speaker: str, *word_speakers: str) -> Segment:
    words = tuple(Word(f"w{i}", float(i), i + 0.5, who) for i, who in enumerate(word_speakers))
    return Segment("system", 0.0, 2.0, "w0 w1", words, speaker)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"type": "note", "text": "  Ask about   budget \\n now "}', Note("Ask about budget now")),
        ('{"type": "rename_speaker", "from": "Speaker 1", "to": "Ana"}', Rename("Speaker 1", "Ana")),
        ('{"type": "note", "text": "   "}', None),
        ('{"type": "note", "text": 5}', None),
        ('{"type": "note", "text": "' + "x" * 2001 + '"}', None),
        ('{"type": "rename_speaker", "from": "Speaker 1", "to": "**Boss**"}', None),
        ('{"type": "rename_speaker", "from": "Speaker 1", "to": "Note"}', None),
        ('{"type": "rename_speaker", "from": "Ana", "to": "Ana"}', None),
        ('{"type": "approve_action", "id": "x"}', None),
        ("not json", None),
        ("[1, 2]", None),
    ],
)
def test_client_messages_are_validated(raw: str, expected) -> None:
    assert parse(raw) == expected


def test_names_are_trimmed_and_limited() -> None:
    assert clean_name("  Ana   Kaya ") == "Ana Kaya"
    for bad in ("", "x" * 41, "a\x00b", "`code`", 7):
        with pytest.raises((TypeError, ValueError)):
            clean_name(bad)


def test_renames_apply_to_segment_and_words_and_can_be_chained() -> None:
    names = SpeakerNames()
    names.rename("Speaker 1", "Ana")
    names.rename("Ana", "Ana K.")
    names.rename("me", "Alp")

    renamed = names.apply(segment("Speaker 1", "Speaker 1", "Speaker 2"))

    assert renamed.speaker == "Ana K."
    assert [word.speaker for word in renamed.words] == ["Ana K.", "Speaker 2"]
    assert names.apply(segment("me")).speaker == "Alp"


def test_note_is_a_markdown_line_with_the_note_speaker() -> None:
    line = markdown_lines(note_segment(Note("Push back on the date"), 65.0))
    assert line == [f"- `00:01:05` **{NOTE_SPEAKER}:** Push back on the date"]


async def test_server_passes_client_text_to_the_handler() -> None:
    received: list[str] = []

    async def on_message(raw: str) -> None:
        received.append(raw)

    async with (
        TranscriptServer(port=0, allowed_origins=[ORIGIN], on_message=on_message) as server,
        connect(f"ws://127.0.0.1:{server.port}", origin=ORIGIN) as client,
    ):
        await client.send('{"type": "note", "text": "hi"}')
        await client.send(b"binary is ignored")
        server.publish_rename("Speaker 1", "Ana")
        renamed = json.loads(await client.recv())
        for _ in range(50):
            if received:
                break
            await asyncio.sleep(0.01)

    assert received == ['{"type": "note", "text": "hi"}']
    assert renamed == {"type": "renamed", "from": "Speaker 1", "to": "Ana"}


async def test_oversized_client_message_closes_the_connection() -> None:
    async def on_message(raw: str) -> None:
        raise AssertionError("must not be called")

    async with (
        TranscriptServer(port=0, allowed_origins=[ORIGIN], on_message=on_message) as server,
        connect(f"ws://127.0.0.1:{server.port}", origin=ORIGIN, max_size=None) as client,
    ):
        await client.send("x" * (MAX_CLIENT_MESSAGE + 1))
        with pytest.raises(ConnectionClosed):
            await asyncio.wait_for(client.recv(), 2)


async def test_handler_errors_do_not_drop_the_connection() -> None:
    async def on_message(raw: str) -> None:
        raise RuntimeError("boom")

    async with (
        TranscriptServer(port=0, allowed_origins=[ORIGIN], on_message=on_message) as server,
        connect(f"ws://127.0.0.1:{server.port}", origin=ORIGIN) as client,
    ):
        await client.send("anything")
        server.publish_rename("a", "b")
        assert json.loads(await client.recv())["type"] == "renamed"


def test_switch_project_is_parsed_and_checked() -> None:
    from recall.live_controls import SwitchProject, parse

    assert parse('{"type": "switch_project", "project": " mobile "}') == SwitchProject("mobile")
    assert parse('{"type": "switch_project", "project": 3}') is None
    assert parse('{"type": "switch_project", "project": ""}') is None


def test_import_documents_is_parsed_and_checked() -> None:
    from recall.live_controls import ImportDocuments, parse

    pdf, md = str(Path("/a/b.pdf").resolve()), str(Path("/c.md").resolve())  # absolute on every OS
    assert parse(json.dumps({"type": "import_documents", "paths": [pdf, f" {md} "]})) == ImportDocuments((pdf, md))
    assert parse('{"type": "import_documents", "paths": ["relative.md"]}') is None
    assert parse('{"type": "import_documents", "paths": []}') is None
    assert parse(json.dumps({"type": "import_documents", "paths": pdf})) is None
    assert parse(json.dumps({"type": "import_documents", "paths": [pdf] * 51})) is None
