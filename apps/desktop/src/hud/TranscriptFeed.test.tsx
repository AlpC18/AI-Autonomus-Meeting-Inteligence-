// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TranscriptFeed } from "./TranscriptFeed";

afterEach(cleanup);

const segment = (text: string, start: number) => ({ source: "system", start, end: start + 1, text, words: [], speaker: "Ayşe" });

describe("TranscriptFeed", () => {
  it("shows a translation under the line it belongs to", () => {
    render(
      <TranscriptFeed
        status="open"
        segments={[segment("Bütçe 35 bin dolar.", 1), segment("Tamam.", 2)]}
        captions={{ "system:1": "The budget is 35 thousand dollars." }}
      />,
    );
    const lines = screen.getAllByRole("listitem").map((item) => item.textContent);
    expect(lines).toEqual(["00:01Ayşe Bütçe 35 bin dolar.", "The budget is 35 thousand dollars.", "00:02Ayşe Tamam."]);
  });

  it("shows people as Person 1 and You, and says when nobody has spoken yet", () => {
    const { rerender } = render(<TranscriptFeed status="open" segments={[]} />);
    expect(screen.getByText("Waiting for someone to speak…")).toBeTruthy();
    rerender(
      <TranscriptFeed
        status="open"
        segments={[
          { source: "system", start: 3, end: 4, text: "Merhaba", words: [], speaker: "Speaker 1" },
          { source: "mic", start: 5, end: 6, text: "Selam", words: [], speaker: "me" },
        ]}
      />,
    );
    expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual(["00:03Person 1 Merhaba", "00:05You Selam"]);
  });
});
