// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { describe, expect, it } from "vitest";
import { parseEngineEvent } from "./transcriptStream";

describe("engine events", () => {
  it("reads answers with their cited sources", () => {
    const event = parseEngineEvent(
      JSON.stringify({
        type: "answer",
        id: "q1",
        text: "It is $35,000 [2].",
        sources: [{ number: 2, speaker: "Ana", text: "Budget is $35,000", spoken_at: "2026-10-01T10:00:00Z", disputed: false }, { number: "x" }],
      }),
    );
    expect(event?.type).toBe("answer");
    if (event?.type === "answer") {
      expect(event.answer.sources).toHaveLength(1);
      expect(event.answer.sources[0].number).toBe(2);
      expect(event.answer.error).toBeNull();
    }
  });

  it("reads summaries, errors and meeting changes", () => {
    expect(parseEngineEvent('{"type":"summary","markdown":"## Summary","queued":2,"errors":["x"]}')).toEqual({
      type: "summary",
      summary: { markdown: "## Summary", queued: 2, errors: ["x"], error: null },
    });
    expect(parseEngineEvent('{"type":"answer","id":"q2","error":"Memory is off"}')).toMatchObject({ answer: { error: "Memory is off" } });
    expect(parseEngineEvent('{"type":"meeting_started","title":"Weekly sync"}')).toEqual({ type: "meeting_started", title: "Weekly sync", project: null });
    expect(parseEngineEvent('{"type":"meeting_started","title":"Sync","project":"web"}')).toMatchObject({ project: "web" });
    expect(parseEngineEvent('{"type":"project_error","error":"Memory is off"}')).toEqual({ type: "project_error", error: "Memory is off" });
    expect(parseEngineEvent('{"type":"meeting_ended"}')).toBeNull();
    expect(parseEngineEvent("nope")).toBeNull();
  });

  it("reads a brief with its cited statements", () => {
    const event = parseEngineEvent(
      '{"type":"brief","title":"Budget","text":"Budget $35,000 [1]","sources":[{"number":1,"speaker":"Ana","text":"Budget is $35,000","spoken_at":"2026-10-01T10:00:00+00:00"}]}',
    );
    expect(event).toMatchObject({ type: "brief", brief: { id: "brief", text: "Budget $35,000 [1]", error: null } });
    expect(parseEngineEvent('{"type":"brief","error":"no calendar title"}')).toMatchObject({ brief: { error: "no calendar title" } });
  });

  it("reads live action items and drops malformed ones", () => {
    const event = parseEngineEvent(
      '{"type":"action_items","items":[{"task":"Send the report","owner":"Ana","due":"2026-11-30"},{"task":"Book a room"},{"owner":"x"},7]}',
    );
    expect(event).toEqual({
      type: "action_items",
      items: [
        { task: "Send the report", owner: "Ana", due: "2026-11-30" },
        { task: "Book a room", owner: null, due: null },
      ],
    });
  });

  it("reads talk time when a meeting ends", () => {
    const event = parseEngineEvent(
      '{"type":"meeting_ended","reason":"user","talk_time":[{"speaker":"Ana","seconds":90,"share":0.75,"longest_seconds":60,"interruptions":2},{"speaker":5}]}',
    );
    expect(event).toEqual({
      type: "meeting_ended",
      reason: "user",
      talkTime: [{ speaker: "Ana", seconds: 90, share: 0.75, longestSeconds: 60, interruptions: 2 }],
      report: null,
    });
    expect(parseEngineEvent('{"type":"meeting_ended","reason":"idle","report":"## Hesitations"}')).toEqual({
      type: "meeting_ended",
      reason: "idle",
      talkTime: [],
      report: "## Hesitations",
    });
  });
});

describe("documents_imported", () => {
  it("reads the imported files and errors, skipping malformed entries", () => {
    expect(
      parseEngineEvent(
        JSON.stringify({ type: "documents_imported", imported: [{ name: "a.md", passages: 3 }, { name: 1 }], errors: ["b: not found", 2] }),
      ),
    ).toEqual({ type: "documents_imported", result: { imported: [{ name: "a.md", passages: 3 }], errors: ["b: not found"] } });
  });
});

describe("translation", () => {
  it("pairs a caption with its segment", () => {
    expect(parseEngineEvent(JSON.stringify({ type: "translation", source: "system", start: 1.5, text: "Hello" }))).toEqual({
      type: "translation",
      key: "system:1.5",
      text: "Hello",
    });
    expect(parseEngineEvent(JSON.stringify({ type: "translation", source: "system", text: "x" }))).toBeNull();
  });
});
