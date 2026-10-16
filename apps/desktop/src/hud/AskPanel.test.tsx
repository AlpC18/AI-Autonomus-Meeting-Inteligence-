// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AskPanel } from "./AskPanel";
import { SpeakerNamer, nameProblem, speakersIn } from "./SpeakerNamer";
import type { Answer, EngineCommand, TranscriptSegment } from "./transcriptStream";

afterEach(cleanup);

describe("AskPanel", () => {
  it("asks the engine and shows the cited answer", () => {
    const sent: EngineCommand[] = [];
    const send = (message: EngineCommand) => (sent.push(message), true);
    const { rerender } = render(<AskPanel connected send={send} answers={{}} />);

    const ask = screen.getByRole("button", { name: "Ask" }) as HTMLButtonElement;
    expect(ask.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "  What is the budget?  " } });
    fireEvent.click(ask);

    expect(sent).toHaveLength(1);
    const command = sent[0];
    expect(command).toMatchObject({ type: "ask", question: "What is the budget?" });
    expect(screen.getByText("Looking through your meetings…")).toBeTruthy();

    const id = command.type === "ask" ? command.id : "";
    const answer: Answer = {
      id,
      text: "It is $35,000 [1].",
      sources: [{ number: 1, speaker: "Ana", text: "Budget is $35,000", spokenAt: new Date("2026-10-01T10:00:00Z"), disputed: true }],
      error: null,
    };
    rerender(<AskPanel connected send={send} answers={{ [id]: answer }} />);
    const status = screen.getByRole("status").textContent;
    expect(status).toContain("It is $35,000 [1].");
    expect(status).toContain("(disputed)");
    expect(status).toContain("“Budget is $35,000”");
  });

  it("shows the engine's error and does not wait when the engine is gone", () => {
    const { rerender } = render(<AskPanel connected={false} send={() => false} answers={{}} />);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "x" } });
    fireEvent.submit(screen.getByLabelText("Question").closest("form")!);
    expect(screen.queryByText("Looking through your meetings…")).toBeNull();

    let id = "";
    const send = (message: EngineCommand) => ((id = message.type === "ask" ? message.id : ""), true);
    rerender(<AskPanel connected send={send} answers={{}} />);
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    rerender(<AskPanel connected send={send} answers={{ [id]: { id, text: "", sources: [], error: "Memory is off" } }} />);
    expect(screen.getByRole("status").textContent).toBe("Memory is off");
  });
});

const seg = (speaker: string, words: Array<[string, string | null]> = []): TranscriptSegment => ({
  source: "system",
  start: 0,
  end: 1,
  text: words.map(([text]) => text).join(" ") || "hi",
  speaker,
  words: words.map(([text, who], index) => ({ text, start: index, end: index + 1, speaker: who })),
});

describe("SpeakerNamer", () => {
  it("lists each speaker once, in order, without typed notes", () => {
    expect(speakersIn([seg("Speaker 1"), seg("Note"), seg("Speaker 2", [["a", "Speaker 2"], ["b", "me"]]), seg("Speaker 1")])).toEqual([
      "Speaker 1",
      "Speaker 2",
      "me",
    ]);
  });

  it("explains names the engine would refuse", () => {
    expect(nameProblem("  ")).toBe("Type a name.");
    expect(nameProblem("x".repeat(41))).toBe("Use at most 40 characters.");
    expect(nameProblem("Ana*")).toContain("Leave out");
    expect(nameProblem("note")).toBe('"Note" is reserved.');
    expect(nameProblem("Ana")).toBeNull();
  });

  it("renames the chosen speaker and reports problems", () => {
    const sent: EngineCommand[] = [];
    let connected = true;
    render(<SpeakerNamer segments={[seg("Speaker 1"), seg("Speaker 2")]} connected send={(message) => (sent.push(message), connected)} />);

    fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    expect(screen.getByRole("status").textContent).toBe("Type a name.");

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "Speaker 2" } });
    fireEvent.change(screen.getByPlaceholderText("e.g. Ana"), { target: { value: "  Ana   Lima " } });
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    expect(sent).toEqual([{ type: "rename_speaker", from: "Speaker 2", to: "Ana Lima" }]);
    expect(screen.getByRole("status").textContent).toBe("Speaker 2 will be shown as Ana Lima.");

    connected = false;
    fireEvent.change(screen.getByPlaceholderText("e.g. Ana"), { target: { value: "Ben" } });
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    expect(screen.getByRole("status").textContent).toBe("The engine is not connected; try again in a moment.");
  });

  it("is hidden until someone has spoken", () => {
    const { container } = render(<SpeakerNamer segments={[seg("Note")]} connected send={() => true} />);
    expect(container.innerHTML).toBe("");
  });
});
