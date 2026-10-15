// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MeetingBar } from "./MeetingBar";
import type { EngineCommand } from "./transcriptStream";

afterEach(cleanup);

function bar(sent: EngineCommand[], connected = true) {
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
});
