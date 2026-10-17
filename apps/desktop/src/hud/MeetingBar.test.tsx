// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const opener = vi.hoisted(() => ({ openUrl: vi.fn() }));
vi.mock("@tauri-apps/plugin-opener", () => opener);
import { setLanguage } from "../i18n";
import { MeetingBar } from "./MeetingBar";
import type { EngineCommand } from "./transcriptStream";

afterEach(cleanup);

function bar(sent: EngineCommand[], connected = true, project: string | null = "web", projectError: string | null = null) {
  return (
    <MeetingBar
      title="Budget review"
      connected={connected}
      send={(message) => {
        sent.push(message);
        return connected;
      }}
      lastSummary={null}
      brief={null}
      liveItems={[{ task: "Send the report", owner: "Ana", due: "2026-11-30" }]}
      lastTalkTime={[{ speaker: "Ana", seconds: 95, share: 0.6, longestSeconds: 40, interruptions: 1 }]}
      project={project}
      projectError={projectError}
    />
  );
}

describe("MeetingBar", () => {
  it("ends the meeting and asks for a brief", () => {
    const sent: EngineCommand[] = [];
    render(bar(sent));

    fireEvent.click(screen.getByRole("button", { name: "End meeting" }));
    fireEvent.click(screen.getByRole("button", { name: "Brief me" }));

    expect(sent).toEqual([{ type: "end_meeting" }, { type: "brief" }]);
    expect((screen.getByRole("button", { name: "Ending…" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows live action items and the last meeting's talk time", () => {
    render(bar([]));
    expect(screen.getByText("Send the report")).toBeTruthy();
    expect(screen.getByText(/Ana, due 2026-11-30/)).toBeTruthy();
    expect(screen.getByRole("table", { name: "Talk time in the last meeting" }).textContent).toContain("1:35 (60%)");
  });

  it("cannot end a meeting while the engine is disconnected", () => {
    const sent: EngineCommand[] = [];
    render(bar(sent, false));
    expect((screen.getByRole("button", { name: "End meeting" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("switches the project for the next meeting", () => {
    const sent: EngineCommand[] = [];
    render(bar(sent));
    expect(screen.getByText("Project: web")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Switch project"), { target: { value: " mobile " } });
    fireEvent.click(screen.getByRole("button", { name: "Switch" }));

    expect(sent).toEqual([{ type: "switch_project", project: "mobile" }]);
  });

  it("hides the project switch when memory is off and shows switch errors", () => {
    render(bar([], true, null, "Memory is off"));
    expect(screen.queryByLabelText("Switch project")).toBeNull();
    expect(screen.getByRole("alert").textContent).toContain("Memory is off");
  });

  it("imports chosen documents and shows what was added", async () => {
    const sent: EngineCommand[] = [];
    const { rerender } = render(
      <MeetingBar
        title="Budget review"
        connected
        send={(message) => {
          sent.push(message);
          return true;
        }}
        lastSummary={null}
        brief={null}
        liveItems={[]}
        lastTalkTime={[]}
        project="web"
        projectError={null}
        pick={() => Promise.resolve(["/docs/pricing.pdf"])}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Add documents…" }));
    await waitFor(() => expect(sent).toEqual([{ type: "import_documents", paths: ["/docs/pricing.pdf"] }]));

    rerender(
      <MeetingBar
        title="Budget review"
        connected
        send={() => true}
        lastSummary={null}
        brief={null}
        liveItems={[]}
        lastTalkTime={[]}
        project="web"
        projectError={null}
        lastImport={{ imported: [{ name: "pricing.pdf", passages: 12 }], errors: ["/x.doc: no Markdown, text or PDF files"] }}
      />,
    );
    const status = screen.getByRole("status", { name: "Document import" }).textContent;
    expect(status).toContain("Added pricing.pdf (12 passages)");
    expect(status).toContain("Not added: /x.doc");
  });

  it("is shown in Turkish when the language is Turkish", () => {
    setLanguage("tr");
    try {
      render(bar([]));
      expect(screen.getByRole("button", { name: "Toplantıyı bitir" })).toBeTruthy();
      expect(screen.getByText("Proje: web")).toBeTruthy();
      expect(screen.getByRole("table", { name: "Son toplantıdaki konuşma süreleri" })).toBeTruthy();
    } finally {
      setLanguage("en");
    }
  });

  it("shows the last summary, what awaits approval and the follow-up e-mail", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    opener.openUrl.mockRejectedValueOnce(new Error("no handler"));
    const summary = { markdown: "## Summary\nBudget agreed.", queued: 2, errors: ["Jira: no project"], error: null, email: { subject: "Follow-up", body: "Hi all" } };
    render(
      <MeetingBar title="Budget review" connected send={() => true} lastSummary={summary} brief={null} liveItems={[]} lastTalkTime={[]} project="web" projectError={null} lastReport="## Hesitations\nBen was unsure." />,
    );

    const text = screen.getByRole("region", { name: "Current meeting" }).textContent;
    expect(text).toContain("Budget agreed.");
    expect(text).toContain("2 proposed action(s) are waiting for your approval below.");
    expect(text).toContain("Not proposed: Jira: no project");
    expect(text).toContain("Ben was unsure.");

    fireEvent.click(screen.getByRole("button", { name: "Copy follow-up email" }));
    expect(await screen.findByText("Copied.")).toBeTruthy();
    expect(writeText).toHaveBeenCalledWith("Follow-up\n\nHi all");

    fireEvent.click(screen.getByRole("button", { name: "Open in mail app" }));
    expect(await screen.findByText("No mail app answered.")).toBeTruthy();
    expect(opener.openUrl).toHaveBeenCalledWith("mailto:?subject=Follow-up&body=Hi%20all");
  });

  it("says when the summary could not be made", () => {
    const summary = { markdown: "", queued: 0, errors: [], error: "No AI provider is set", email: null };
    render(<MeetingBar title="x" connected send={() => true} lastSummary={summary} brief={null} liveItems={[]} lastTalkTime={[]} project={null} projectError={null} />);
    expect(screen.getByText("The summary could not be made: No AI provider is set")).toBeTruthy();
  });

  it("says when the transcript is being made accurate", () => {
    render(<MeetingBar title="x" connected send={() => true} lastSummary={null} brief={null} liveItems={[]} lastTalkTime={[]} project={null} projectError={null} polishing />);
    expect(screen.getByText(/Making the transcript accurate/)).toBeTruthy();
  });
});
