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
    expect(parseEngineEvent('{"type":"meeting_started","title":"Weekly sync"}')).toEqual({ type: "meeting_started", title: "Weekly sync" });
    expect(parseEngineEvent('{"type":"meeting_ended"}')).toBeNull();
    expect(parseEngineEvent("nope")).toBeNull();
  });
});
