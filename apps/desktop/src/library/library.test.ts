// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { describe, expect, it } from "vitest";
import { filterLines, formatTime, parseMeeting, parseMeetingList, parseSearchHits } from "./library";

describe("meeting library replies", () => {
  it("keeps only well-formed meetings", () => {
    expect(
      parseMeetingList([
        { path: "/n/a.md", title: "A", modified: "2026-10-14T10:00:00+00:00", has_summary: true },
        { path: 5, title: "broken" },
        "nonsense",
      ]),
    ).toEqual([{ path: "/n/a.md", title: "A", modified: "2026-10-14T10:00:00+00:00", hasSummary: true }]);
    expect(parseMeetingList({ error: "x" })).toEqual([]);
  });

  it("reads a meeting and drops malformed lines", () => {
    const meeting = parseMeeting({
      path: "/n/a.md",
      title: "A",
      audio: null,
      summary: "## Summary",
      lines: [{ time: 4, speaker: "Ana", text: "hi" }, { time: "4" }],
    });
    expect(meeting?.lines).toEqual([{ time: 4, speaker: "Ana", text: "hi" }]);
    expect(meeting?.audio).toBeNull();
    expect(parseMeeting({ path: "/n/a.md" })).toBeNull();
  });

  it("reads search hits", () => {
    expect(parseSearchHits([{ path: "/n/a.md", title: "A", time: 3, speaker: "me", text: "budget" }, {}])).toHaveLength(1);
  });

  it("formats times and filters lines", () => {
    expect(formatTime(65)).toBe("1:05");
    expect(formatTime(3725)).toBe("1:02:05");
    const lines = [
      { time: 1, speaker: "Ana", text: "The Budget" },
      { time: 2, speaker: "Mark", text: "lunch" },
    ];
    expect(filterLines(lines, "budget").map((line) => line.time)).toEqual([1]);
    expect(filterLines(lines, "mark").map((line) => line.time)).toEqual([2]);
    expect(filterLines(lines, "  ")).toHaveLength(2);
  });
});
