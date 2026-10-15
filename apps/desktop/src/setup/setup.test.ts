// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { describe, expect, it } from "vitest";
import { setupComplete, setupSteps } from "./setup";

const view = (values: Record<string, string>, secretsSet: string[] = []) => ({ fields: [], values, secretsSet });

describe("first-run checklist", () => {
  it("starts with everything to do", () => {
    const steps = setupSteps(view({}), false);
    expect(steps.filter((step) => step.done)).toEqual([]);
    expect(setupComplete(steps)).toBe(false);
  });

  it("is complete when the required steps are done, without the optional one", () => {
    const steps = setupSteps(
      view({ CONTINUUM_LLM_PROVIDER: "ollama", CONTINUUM_TENANT_ID: "me", CONTINUUM_PROJECT_ID: "work", CONTINUUM_NOTES_DIR: "~/Notes" }),
      true,
    );
    expect(setupComplete(steps)).toBe(true);
    expect(steps.find((step) => step.id === "speakers")?.done).toBe(false);
  });

  it("needs an API key for cloud providers", () => {
    const withoutKey = setupSteps(view({ CONTINUUM_LLM_PROVIDER: "groq" }), false);
    const withKey = setupSteps(view({ CONTINUUM_LLM_PROVIDER: "groq" }, ["CONTINUUM_LLM_API_KEY"]), false);
    expect(withoutKey.find((step) => step.id === "ai")?.done).toBe(false);
    expect(withKey.find((step) => step.id === "ai")?.done).toBe(true);
  });
});
