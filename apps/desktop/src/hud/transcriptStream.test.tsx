// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MAX_ALERTS, parseSegmentMessage, useTranscriptStream } from "./transcriptStream";
import { parseAlertMessage } from "./factCheck";
import { FakeSocket } from "./fakeSocket.test.helper";

const segment = (text: string, speaker = "Speaker 1", start = 0) => ({
  type: "segment",
  segment: { source: "system", start, end: start + 1, text, speaker, words: [] },
});

const alert = (statement: string) => ({
  type: "fact_check",
  alert: {
    statement,
    speaker: "Ana",
    claimed: ["$50,000"],
    recorded: ["$35,000"],
    record_text: "Budget is $35,000",
    record_speaker: "Ben",
    record_spoken_at: "2026-10-01T10:00:00Z",
  },
});

beforeEach(() => {
  FakeSocket.all = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function connect() {
  const hook = renderHook(() => useTranscriptStream("ws://test"));
  const socket = FakeSocket.all[0];
  act(() => socket.open());
  return { hook, socket };
}

describe("useTranscriptStream", () => {
  it("collects segments, renames speakers and sends commands once open", () => {
    const { hook, socket } = connect();
    expect(hook.result.current.status).toBe("open");

    act(() => {
      socket.push(segment("Hello there"));
      socket.push({ type: "renamed", from: "Speaker 1", to: "Ana" });
    });
    expect(hook.result.current.segments.map((s) => [s.speaker, s.text])).toEqual([["Ana", "Hello there"]]);

    expect(hook.result.current.send({ type: "brief" })).toBe(true);
    expect(socket.sent).toEqual(['{"type":"brief"}']);
  });

  it("keeps only the newest alerts and lets them be dismissed", () => {
    const { hook, socket } = connect();
    act(() => {
      for (let i = 0; i < MAX_ALERTS + 2; i++) socket.push(alert(`Budget is $50,000 (${i})`));
    });
    const shown = hook.result.current.alerts;
    expect(shown).toHaveLength(MAX_ALERTS);
    expect(shown[shown.length - 1].alert.statement).toBe(`Budget is $50,000 (${MAX_ALERTS + 1})`);

    act(() => hook.result.current.dismissAlert(shown[0].id));
    expect(hook.result.current.alerts).toHaveLength(MAX_ALERTS - 1);
  });

  it("shows hints and dismisses them", () => {
    const { hook, socket } = connect();
    act(() => socket.push({ type: "hint", hint: { kind: "code", title: "Paddle", body: "Used in 3 files", details: ["a.py"] } }));
    const [hint] = hook.result.current.hints;
    expect(hint.hint.title).toBe("Paddle");
    act(() => hook.result.current.dismissHint(hint.id));
    expect(hook.result.current.hints).toEqual([]);
  });

  it("follows the meeting lifecycle and engine events", () => {
    const { hook, socket } = connect();
    act(() => {
      socket.push(segment("Left over"));
      socket.push({ type: "action_items", items: [{ task: "Old" }] });
      socket.push({ type: "meeting_started", title: "Weekly sync", project: "web" });
    });
    let state = hook.result.current;
    expect([state.meetingTitle, state.project, state.segments, state.liveItems]).toEqual(["Weekly sync", "web", [], []]);

    act(() => {
      socket.push({ type: "answer", id: "q1", text: "It is $35,000." });
      socket.push({ type: "brief", title: "Weekly sync", text: "Brief" });
      socket.push({ type: "action_items", items: [{ task: "Send the report" }] });
      socket.push({ type: "translation", source: "system", start: 1.5, text: "Merhaba" });
      socket.push({ type: "documents_imported", imported: [{ name: "a.md", passages: 3 }], errors: [] });
      socket.push({ type: "project_error", error: "Memory is off" });
      socket.push({ type: "summary", markdown: "## Summary" });
      socket.push({ type: "meeting_ended", reason: "user", report: "## Hesitations" });
    });
    state = hook.result.current;
    expect(state.answers.q1.text).toBe("It is $35,000.");
    expect(state.brief?.text).toBe("Brief");
    expect(state.liveItems.map((item) => item.task)).toEqual(["Send the report"]);
    expect(state.captions["system:1.5"]).toBe("Merhaba");
    expect(state.lastImport?.imported[0].name).toBe("a.md");
    expect(state.projectError).toBe("Memory is off");
    expect(state.lastSummary?.markdown).toBe("## Summary");
    expect(state.lastReport).toBe("## Hesitations");
  });

  it("ignores garbage and reconnects when the engine goes away", () => {
    const { hook, socket } = connect();
    act(() => socket.onmessage?.({ data: "not json" }));
    expect(hook.result.current.segments).toEqual([]);

    act(() => socket.drop());
    expect(hook.result.current.status).toBe("closed");
    expect(hook.result.current.send({ type: "brief" })).toBe(false);

    act(() => vi.advanceTimersByTime(2000));
    expect(FakeSocket.all).toHaveLength(2);
    expect(hook.result.current.status).toBe("connecting");
  });

  it("stops reconnecting after unmount", () => {
    const { hook, socket } = connect();
    hook.unmount();
    act(() => {
      socket.drop();
      vi.advanceTimersByTime(5000);
    });
    expect(FakeSocket.all).toHaveLength(1);
  });
});

describe("message parsing", () => {
  it("rejects segments with missing or mistyped fields", () => {
    expect(parseSegmentMessage(JSON.stringify(segment("ok")))?.text).toBe("ok");
    expect(parseSegmentMessage(JSON.stringify({ type: "segment", segment: { text: "x" } }))).toBeNull();
    expect(parseSegmentMessage(JSON.stringify({ type: "segment", segment: { ...segment("x").segment, words: [{ text: 1 }] } }))).toBeNull();
    expect(parseSegmentMessage(42)).toBeNull();
  });

  it("reads fact-check alerts and rejects malformed ones", () => {
    const parsed = parseAlertMessage(JSON.stringify(alert("Budget is $50,000")));
    expect(parsed).toMatchObject({ claimed: ["$50,000"], recordSpeaker: "Ben", explanation: "" });
    expect(parsed?.recordSpokenAt.toISOString()).toBe("2026-10-01T10:00:00.000Z");
    expect(parseAlertMessage(JSON.stringify({ type: "fact_check", alert: { statement: "x" } }))).toBeNull();
    expect(parseAlertMessage("{")).toBeNull();
    expect(parseAlertMessage(null)).toBeNull();
  });
});
