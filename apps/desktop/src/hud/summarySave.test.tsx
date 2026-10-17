// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.
// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { clearMocks, mockIPC } from "@tauri-apps/api/mocks";
import { SaveConversation, conversationMarkdown } from "./SaveConversation";
import { SummaryPage } from "./SummaryPage";
import { timeOfDay } from "./TranscriptFeed";
import type { TranscriptSegment } from "./transcriptStream";

afterEach(() => {
  cleanup();
  clearMocks();
});

const NOON = new Date(2026, 9, 18, 12, 0, 0);
const line = (text: string, seconds: number, speaker = "Speaker 1"): TranscriptSegment => ({
  source: "system", start: seconds, end: seconds + 1, text, words: [], speaker, at: NOON.getTime() + seconds * 1000,
});

describe("conversationMarkdown", () => {
  it("writes the timeline and two-minute blocks of who said what", () => {
    const markdown = conversationMarkdown(
      "Weekly sync",
      [line("Bütçe 35 bin.", 5), line("Tamam.", 20, "me"), line("Lansman cuma.", 130)],
      { "system:5": "Budget is 35k." },
      [{ at: NOON.toISOString(), title: "Bütçe" }],
      NOON,
    );
    expect(markdown).toContain("# Weekly sync");
    expect(markdown).toContain(`- ${timeOfDay(NOON.getTime())} Bütçe`);
    expect(markdown).toContain(`### ${timeOfDay(NOON.getTime())} – ${timeOfDay(NOON.getTime() + 120_000)}`);
    expect(markdown).toContain("**Person 1:** Bütçe 35 bin.\n> Budget is 35k.");
    expect(markdown).toContain("**You:** Tamam.");
    expect(markdown.indexOf("Lansman cuma.")).toBeGreaterThan(markdown.indexOf(`### ${timeOfDay(NOON.getTime() + 120_000)}`));
  });
});

describe("SaveConversation", () => {
  it("saves the transcript to the file the user picked", async () => {
    const calls: Array<[string, unknown]> = [];
    mockIPC((command, payload) => {
      calls.push([command, payload]);
      if (command === "plugin:dialog|save") return "/Users/ana/Weekly sync.md";
      return null;
    });
    render(<SaveConversation title="Weekly sync" segments={[line("Merhaba", 1)]} captions={{}} topics={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "Save conversation" }));

    expect(await screen.findByRole("status")).toBeTruthy();
    const [, saved] = calls.find(([command]) => command === "save_transcript")!;
    expect(saved).toMatchObject({ path: "/Users/ana/Weekly sync.md" });
    expect((saved as { text: string }).text).toContain("**Person 1:** Merhaba");
  });

  it("does nothing when the dialog is cancelled and shows why saving failed", async () => {
    let pick: string | null = null;
    mockIPC((command) => {
      if (command === "plugin:dialog|save") return pick;
      throw new Error("Could not save the conversation: disk full");
    });
    render(<SaveConversation title="Sync" segments={[line("Merhaba", 1)]} captions={{}} topics={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "Save conversation" }));
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());

    pick = "/Users/ana/Sync.md";
    fireEvent.click(screen.getByRole("button", { name: "Save conversation" }));
    expect((await screen.findByRole("alert")).textContent).toContain("disk full");
  });
});

describe("SummaryPage", () => {
  it("offers to end the meeting when there is no summary yet, and goes back", () => {
    const sent: unknown[] = [];
    const back = vi.fn();
    render(<SummaryPage connected send={(message) => sent.push(message) > 0} summary={null} polishing={false} topics={[]} back={back} />);
    fireEvent.click(screen.getByRole("button", { name: "End meeting and summarize" }));
    expect(sent).toEqual([{ type: "end_meeting" }]);
    fireEvent.click(screen.getByRole("button", { name: "Back to the live meeting" }));
    expect(back).toHaveBeenCalled();
  });

  it("shows the summary once it arrives", () => {
    const summary = { markdown: "## Decisions\n- Launch Friday", queued: 0, errors: [], error: null };
    render(<SummaryPage connected send={() => true} summary={summary} polishing={false} topics={[]} back={() => undefined} />);
    expect(screen.getByText(/Launch Friday/)).toBeTruthy();
  });
});
