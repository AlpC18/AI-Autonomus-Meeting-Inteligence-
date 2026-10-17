// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { describe, expect, it } from "vitest";
import { fieldShown, setupComplete, setupSteps, stepSave } from "./setup";

const view = (values: Record<string, string>, secretsSet: string[] = []) => ({ fields: [], values, secretsSet });

describe("first-run checklist", () => {
  it("starts with everything to do", () => {
    const steps = setupSteps(view({}), false);
    expect(steps.filter((step) => step.done)).toEqual([]);
    expect(setupComplete(steps)).toBe(false);
  });

  it("is complete when the required steps are done, without the optional one", () => {
    const steps = setupSteps(
      view({ RECALL_LLM_PROVIDER: "ollama", RECALL_TENANT_ID: "me", RECALL_PROJECT_ID: "work", RECALL_NOTES_DIR: "~/Notes" }),
      true,
    );
    expect(setupComplete(steps)).toBe(true);
    expect(steps.find((step) => step.id === "speakers")?.done).toBe(false);
  });

  it("needs an API key for cloud providers", () => {
    const withoutKey = setupSteps(view({ RECALL_LLM_PROVIDER: "groq" }), false);
    const withKey = setupSteps(view({ RECALL_LLM_PROVIDER: "groq" }, ["RECALL_LLM_API_KEY"]), false);
    expect(withoutKey.find((step) => step.id === "ai")?.done).toBe(false);
    expect(withKey.find((step) => step.id === "ai")?.done).toBe(true);
  });

  it("saves one step's fields without losing other settings or untouched secrets", () => {
    const settings = {
      fields: [
        { key: "RECALL_LLM_PROVIDER", label: "", group: "", kind: "choice" as const, options: [], help: "" },
        { key: "RECALL_LLM_API_KEY", label: "", group: "", kind: "secret" as const, options: [], help: "" },
      ],
      values: { RECALL_NOTES_DIR: "~/Notes", RECALL_LLM_PROVIDER: "ollama" },
      secretsSet: [],
    };
    expect(stepSave(settings, { RECALL_LLM_PROVIDER: "groq ", RECALL_LLM_API_KEY: " gsk-1 " })).toEqual({
      values: { RECALL_NOTES_DIR: "~/Notes", RECALL_LLM_PROVIDER: "groq" },
      secrets: { RECALL_LLM_API_KEY: "gsk-1" },
    });
    expect(stepSave(settings, { RECALL_LLM_API_KEY: "" }).secrets).toEqual({});
  });

  it("asks for an API key only for cloud providers", () => {
    const settings = view({ RECALL_LLM_PROVIDER: "groq" });
    expect(fieldShown("RECALL_LLM_API_KEY", {}, settings)).toBe(true);
    expect(fieldShown("RECALL_LLM_API_KEY", { RECALL_LLM_PROVIDER: "ollama" }, settings)).toBe(false);
    expect(fieldShown("RECALL_TENANT_ID", {}, settings)).toBe(true);
  });
});
