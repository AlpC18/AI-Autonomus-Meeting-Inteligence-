// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.
// @vitest-environment jsdom

import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { clearMocks, mockIPC } from "@tauri-apps/api/mocks";
import { EngineButton } from "../EngineButton";
import { MeetingLanguages, codesOf } from "./MeetingLanguages";
import { Timeline, timeOf } from "./Timeline";
import { displaySpeaker, speakerColor } from "./speakers";

afterEach(() => {
  cleanup();
  clearMocks();
});

describe("speakers", () => {
  it("shows engine labels as people and keeps a colour per person", () => {
    expect(displaySpeaker("Speaker 3")).toBe("Person 3");
    expect(displaySpeaker("me")).toBe("You");
    expect(displaySpeaker("others")).toBe("Others");
    expect(displaySpeaker("Ayşe")).toBe("Ayşe");
    expect(speakerColor("Speaker 1")).toBe(speakerColor("Speaker 1"));
    expect(speakerColor("me")).toBe("text-zinc-900");
  });
});

describe("Timeline", () => {
  it("lists what was talked about from what time", () => {
    const at = "2026-10-17T08:05:00Z";
    render(<Timeline topics={[{ at, title: "Bütçe ve lansman tarihi" }]} />);
    expect(screen.getByText("Bütçe ve lansman tarihi")).toBeTruthy();
    expect(screen.getByText(timeOf(at))).toBeTruthy();
    expect(timeOf("not a time")).toBe("");
  });

  it("explains itself before the first entry", () => {
    render(<Timeline topics={[]} />);
    expect(screen.getByText(/every two minutes/)).toBeTruthy();
  });
});

describe("MeetingLanguages", () => {
  const settings = { fields: [], values: { RECALL_MEETING_LANGUAGES: "en,tr" }, secretsSet: [] };

  it("reads the saved codes", () => {
    expect(codesOf(" EN, tr ,,sq")).toEqual(["en", "tr", "sq"]);
    expect(codesOf(undefined)).toEqual([]);
  });

  it("saves the chosen languages", async () => {
    const saved: unknown[] = [];
    mockIPC((command, payload) => {
      if (command === "save_settings") saved.push(payload);
      return [];
    });
    let reloads = 0;
    render(<MeetingLanguages settings={settings} saved={() => (reloads += 1)} />);
    expect(screen.getByRole("button", { name: "Türkçe" }).getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "Shqip" }));
    fireEvent.click(screen.getByRole("button", { name: "Save languages" }));

    await waitFor(() => expect(reloads).toBe(1));
    expect(saved).toEqual([{ values: { RECALL_MEETING_LANGUAGES: "en,tr,sq" }, secrets: {} }]);
    expect(screen.getByRole("status").textContent).toContain("stay in these languages");
  });
});

describe("EngineButton", () => {
  it("starts a stopped engine and stops a running one", async () => {
    const commands: string[] = [];
    mockIPC((command) => {
      commands.push(command);
    });
    const { rerender } = render(<EngineButton status="closed" />);
    fireEvent.click(screen.getByRole("button", { name: "Start engine" }));
    expect(screen.getByRole("button", { name: "Starting…" })).toBeTruthy();
    await waitFor(() => expect(commands).toEqual(["engine_start"]));

    rerender(<EngineButton status="open" />);
    fireEvent.click(screen.getByRole("button", { name: "Stop engine" }));
    await waitFor(() => expect(commands).toEqual(["engine_start", "engine_stop"]));
  });

  it("shows why the engine could not start", async () => {
    mockIPC(() => {
      throw new Error("The engine folder is not configured.");
    });
    render(<EngineButton status="closed" />);
    fireEvent.click(screen.getByRole("button", { name: "Start engine" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Start engine" })).toBeTruthy();
  });
});
