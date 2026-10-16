// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FactCheckCard } from "./FactCheckCard";
import { HintCard } from "./HintCard";
import { Notepad } from "../notes/Notepad";
import type { EngineCommand } from "./transcriptStream";

afterEach(cleanup);

const alert = {
  statement: "The budget is $50,000",
  speaker: "Ana",
  claimed: ["$50,000"],
  recorded: ["$35,000"],
  recordText: "Budget is $35,000",
  recordSpeaker: "Ben",
  recordSpokenAt: new Date("2026-10-01T10:00:00Z"),
  explanation: "",
};

describe("FactCheckCard", () => {
  it("puts the figures said now next to the record, and can be dismissed", () => {
    const onDismiss = vi.fn();
    render(<FactCheckCard alert={alert} onDismiss={onDismiss} />);
    const card = screen.getByRole("status").textContent;
    expect(card).toContain("$50,000");
    expect(card).toContain("$35,000");
    expect(card).toContain("“Budget is $35,000”");
    expect(card).toContain("Ben, ");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss fact check" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("shows the AI's explanation for contradictions without figures, and copes with a bad date", () => {
    render(<FactCheckCard alert={{ ...alert, claimed: [], explanation: "Ben said launch is in March", recordSpokenAt: new Date("x") }} onDismiss={() => {}} />);
    const card = screen.getByRole("status").textContent;
    expect(card).toContain("“The budget is $50,000”");
    expect(card).toContain("Ben said launch is in March");
    expect(card).toContain("Ben, earlier");
  });
});

describe("HintCard", () => {
  it("labels the hint by kind and lists its details", () => {
    const onDismiss = vi.fn();
    render(<HintCard hint={{ kind: "commitment", title: "Ana took on a 4th task", body: "She has 3 open", details: ["#12", "#14"] }} onDismiss={onDismiss} />);
    expect(screen.getByText("Commitment risk")).toBeTruthy();
    expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual(["#12", "#14"]);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss commitment risk" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});

describe("Notepad", () => {
  it("adds a note on Enter, keeps Shift+Enter as a new line", () => {
    const sent: EngineCommand[] = [];
    render(<Notepad connected send={(message) => (sent.push(message), true)} />);
    const box = screen.getByRole("textbox") as HTMLTextAreaElement;

    fireEvent.change(box, { target: { value: "  Push back on December  " } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(sent).toEqual([]);
    fireEvent.keyDown(box, { key: "Enter" });

    expect(sent).toEqual([{ type: "note", text: "Push back on December" }]);
    expect(box.value).toBe("");
  });

  it("keeps the note when the engine is gone", () => {
    render(<Notepad connected={false} send={() => false} />);
    const box = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(screen.getByText("Waiting for the engine…")).toBeTruthy();
    fireEvent.change(box, { target: { value: "Keep me" } });
    fireEvent.submit(box.closest("form")!);
    expect(screen.getByRole("alert").textContent).toContain("your note was kept here");
    expect(box.value).toBe("Keep me");
  });
});
