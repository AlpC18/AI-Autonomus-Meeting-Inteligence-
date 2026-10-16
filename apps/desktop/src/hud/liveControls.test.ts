// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { describe, expect, it } from "vitest";
import { nameProblem, speakersIn } from "./SpeakerNamer";
import { parseRenamedMessage, renameInSegment, type TranscriptSegment } from "./transcriptStream";

const segment = (speaker: string, source = "system"): TranscriptSegment => ({
  source,
  start: 0,
  end: 1,
  text: "hello there",
  speaker,
  words: [
    { text: "hello", start: 0, end: 0.5, speaker },
    { text: "there", start: 0.5, end: 1, speaker: "Speaker 2" },
  ],
});

describe("speaker renames", () => {
  it("reads only well-formed rename messages", () => {
    expect(parseRenamedMessage('{"type":"renamed","from":"Speaker 1","to":"Ana"}')).toEqual({
      from: "Speaker 1",
      to: "Ana",
    });
    expect(parseRenamedMessage('{"type":"renamed","from":"Speaker 1"}')).toBeNull();
    expect(parseRenamedMessage("not json")).toBeNull();
    expect(parseRenamedMessage(42)).toBeNull();
  });

  it("relabels the segment and its words without touching others", () => {
    const renamed = renameInSegment(segment("Speaker 1"), { from: "Speaker 1", to: "Ana" });
    expect(renamed.speaker).toBe("Ana");
    expect(renamed.words.map((word) => word.speaker)).toEqual(["Ana", "Speaker 2"]);
  });

  it("lists speakers in order of appearance, without typed notes", () => {
    const note: TranscriptSegment = { ...segment("Note", "note"), words: [] };
    expect(speakersIn([segment("Speaker 1"), note, segment("me")])).toEqual(["Speaker 1", "Speaker 2", "me"]);
  });

  it("explains unusable names", () => {
    expect(nameProblem("  Ana ")).toBeNull();
    expect(nameProblem("")).not.toBeNull();
    expect(nameProblem("x".repeat(41))).not.toBeNull();
    expect(nameProblem("**Boss**")).not.toBeNull();
    expect(nameProblem("note")).not.toBeNull();
  });
});
