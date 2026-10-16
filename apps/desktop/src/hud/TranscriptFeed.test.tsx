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
    expect(lines).toEqual(["Ayşe: Bütçe 35 bin dolar.", "The budget is 35 thousand dollars.", "Ayşe: Tamam."]);
  });
});
