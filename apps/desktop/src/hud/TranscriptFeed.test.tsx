// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TranscriptFeed, timeOfDay, transcriptBlocks } from "./TranscriptFeed";
import type { TranscriptSegment } from "./transcriptStream";

afterEach(cleanup);

const NOON = new Date(2026, 9, 18, 12, 0, 0).getTime();
const at = (minutes: number, seconds = 0) => NOON + (minutes * 60 + seconds) * 1000;
const segment = (text: string, start: number, speaker = "Ayşe", wall = at(0, start)): TranscriptSegment => ({
  source: "system", start, end: start + 1, text, words: [], speaker, at: wall,
});

describe("transcriptBlocks", () => {
  it("joins two minutes of clock time into one block, one paragraph per person in a row", () => {
    const blocks = transcriptBlocks([
      segment("Bütçe 35 bin dolar.", 1),
      segment("Tamam.", 50),
      segment("Ben de katılıyorum.", 70, "me"),
      segment("Lansman cuma.", 130, "Ayşe", at(2, 10)),
    ]);
    expect(blocks.map((block) => block.from)).toEqual([NOON, at(2)]);
    expect(blocks[0].paragraphs.map((p) => [p.speaker, p.text])).toEqual([
      ["Ayşe", "Bütçe 35 bin dolar. Tamam."],
      ["me", "Ben de katılıyorum."],
    ]);
  });
});

describe("TranscriptFeed", () => {
  it("heads each block with its clock times and keeps translations with the paragraph", () => {
    render(
      <TranscriptFeed
        status="open"
        segments={[segment("Bütçe 35 bin dolar.", 1), segment("Tamam.", 2)]}
        captions={{ "system:1": "The budget is 35 thousand dollars." }}
      />,
    );
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe(`${timeOfDay(NOON)} – ${timeOfDay(at(2))}`);
    expect(screen.getByText("Bütçe 35 bin dolar. Tamam.")).toBeTruthy();
    expect(screen.getByLabelText("Translation").textContent).toBe("The budget is 35 thousand dollars.");
  });

  it("shows people as Person 1 and You, and says when nobody has spoken yet", () => {
    const { rerender } = render(<TranscriptFeed status="open" segments={[]} />);
    expect(screen.getByText("Waiting for someone to speak…")).toBeTruthy();
    rerender(<TranscriptFeed status="open" segments={[segment("Merhaba", 3, "Speaker 1"), { ...segment("Selam", 5, "me"), source: "mic" }]} />);
    expect(screen.getByText("Person 1")).toBeTruthy();
    expect(screen.getByText("You")).toBeTruthy();
  });
});
