// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { HintCard } from "./HintCard";
import { parseHintMessage } from "./hints";

afterEach(cleanup);

describe("hints", () => {
  it("parses well-formed hints only", () => {
    const raw = JSON.stringify({
      type: "hint",
      hint: { kind: "code", title: "Code context: paddle", body: "3 files", details: ["a.py", 4, "b.py"] },
    });
    expect(parseHintMessage(raw)).toEqual({ kind: "code", title: "Code context: paddle", body: "3 files", details: ["a.py", "b.py"] });
    expect(parseHintMessage('{"type":"hint","hint":{"kind":"evil","title":"x","body":"y"}}')).toBeNull();
    expect(parseHintMessage('{"type":"segment"}')).toBeNull();
    expect(parseHintMessage("nope")).toBeNull();
  });

  it("shows a hint with its files and can be dismissed", () => {
    let dismissed = false;
    render(
      <HintCard
        hint={{ kind: "code", title: "Code context: paddle", body: "3 files", details: ["services/payment/checkout.py"] }}
        onDismiss={() => {
          dismissed = true;
        }}
      />,
    );
    expect(screen.getByText("services/payment/checkout.py")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss code context" }));
    expect(dismissed).toBe(true);
  });
});
