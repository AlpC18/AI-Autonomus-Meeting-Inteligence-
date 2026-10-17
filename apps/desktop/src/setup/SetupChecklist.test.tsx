// @vitest-environment jsdom
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { clearMocks, mockIPC } from "@tauri-apps/api/mocks";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SetupChecklist } from "./SetupChecklist";
import { setupSteps } from "./setup";

afterEach(() => {
  cleanup();
  clearMocks();
});

const field = (key: string, label: string, kind: string, options: string[] = []) => ({ key, label, group: "", kind, options, help: "" });
const SETTINGS = {
  fields: [
    field("RECALL_LLM_PROVIDER", "AI provider", "choice", ["", "groq", "ollama"]),
    field("RECALL_LLM_API_KEY", "API key", "secret"),
    field("RECALL_TENANT_ID", "Workspace", "text"),
    field("RECALL_PROJECT_ID", "Project", "text"),
    field("RECALL_NOTES_DIR", "Notes folder", "text"),
    field("HF_TOKEN", "Hugging Face token", "secret"),
  ] as never,
  values: { RECALL_NOTES_DIR: "~/Notes" },
  secretsSet: [],
};

describe("SetupChecklist", () => {
  it("saves a step from the checklist, keeping the other settings", async () => {
    const saves: unknown[] = [];
    mockIPC((cmd, args) => {
      if (cmd === "save_settings") {
        saves.push(args);
        return [];
      }
      throw new Error(`unexpected command ${cmd}`);
    });
    let reloads = 0;
    render(
      <SetupChecklist
        steps={setupSteps(SETTINGS, false)}
        settings={SETTINGS}
        saved={() => reloads++}
        openSettings={() => undefined}
        dismiss={() => undefined}
      />,
    );

    const ai = screen.getByText("Choose an AI provider").closest("li") as HTMLElement;
    fireEvent.change(within(ai).getByRole("combobox"), { target: { value: "groq" } });
    fireEvent.change(within(ai).getByLabelText("API key"), { target: { value: "gsk-1" } });
    fireEvent.click(within(ai).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(reloads).toBe(1));
    expect(saves).toEqual([
      { values: { RECALL_NOTES_DIR: "~/Notes", RECALL_LLM_PROVIDER: "groq" }, secrets: { RECALL_LLM_API_KEY: "gsk-1" } },
    ]);
  });

  it("does not ask for a key for a local AI and hides forms of finished steps", () => {
    render(
      <SetupChecklist
        steps={setupSteps(SETTINGS, false)}
        settings={SETTINGS}
        saved={() => undefined}
        openSettings={() => undefined}
        dismiss={() => undefined}
      />,
    );
    const ai = screen.getByText("Choose an AI provider").closest("li") as HTMLElement;
    fireEvent.change(within(ai).getByRole("combobox"), { target: { value: "ollama" } });
    expect(within(ai).queryByLabelText("API key")).toBeNull();
    const notes = screen.getByText("Pick a notes folder").closest("li") as HTMLElement;
    expect(within(notes).queryByRole("button", { name: "Save" })).toBeNull();
  });
});
