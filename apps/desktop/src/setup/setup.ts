// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import type { SettingsView } from "../settings/settings";

/** One thing to do before the first meeting. */
export interface SetupStep {
  id: "permissions" | "ai" | "memory" | "notes" | "speakers";
  title: string;
  help: string;
  done: boolean;
  /** Optional steps do not keep the setup screen open. */
  optional: boolean;
}

/** AI providers that run on this computer and need no API key. */
const LOCAL_PROVIDERS = new Set(["ollama", "lmstudio"]);

/**
 * The first-run checklist from the current settings. `heardSpeech` is whether
 * the engine has transcribed anything yet, which shows that the microphone
 * (and on macOS the screen-recording permission for system audio) works.
 */
export function setupSteps(settings: SettingsView, heardSpeech: boolean): SetupStep[] {
  const value = (key: string) => (settings.values[key] ?? "").trim();
  const provider = value("RECALL_LLM_PROVIDER");
  return [
    {
      id: "permissions",
      title: "Let Recall hear the meeting",
      help: "macOS asks for Microphone and Screen Recording (for the other people's audio). Allow both, then say something: this step is done when your words appear in the Live view.",
      done: heardSpeech,
      optional: false,
    },
    {
      id: "ai",
      title: "Choose an AI provider",
      help: "Used for summaries, answers and briefs. Groq and Gemini have free keys; Ollama runs on this computer with no key.",
      done: provider !== "" && (LOCAL_PROVIDERS.has(provider) || settings.secretsSet.includes("RECALL_LLM_API_KEY")),
      optional: false,
    },
    {
      id: "memory",
      title: "Name your workspace and project",
      help: "Meetings are remembered per workspace and project, so you can ask about them later.",
      done: value("RECALL_TENANT_ID") !== "" && value("RECALL_PROJECT_ID") !== "",
      optional: false,
    },
    {
      id: "notes",
      title: "Pick a notes folder",
      help: "Each meeting is also saved there as a Markdown file (an Obsidian vault folder works well).",
      done: value("RECALL_NOTES_DIR") !== "",
      optional: false,
    },
    {
      id: "speakers",
      title: "Tell speakers apart (optional)",
      help: "A free Hugging Face token lets Recall separate and recognise the other people in a call.",
      done: settings.secretsSet.includes("HF_TOKEN"),
      optional: true,
    },
  ];
}

/** Whether every required step is done. */
export function setupComplete(steps: readonly SetupStep[]): boolean {
  return steps.every((step) => step.done || step.optional);
}

/** System Settings panes for the two permissions the engine needs on macOS. */
export const PRIVACY_PANES = {
  Microphone: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
  "Screen Recording": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
} as const;

/** The settings each step can be completed with, right in the checklist. */
export const STEP_FIELDS: Record<SetupStep["id"], readonly string[]> = {
  permissions: [],
  ai: ["RECALL_LLM_PROVIDER", "RECALL_LLM_API_KEY"],
  memory: ["RECALL_TENANT_ID", "RECALL_PROJECT_ID"],
  notes: ["RECALL_NOTES_DIR"],
  speakers: ["HF_TOKEN"],
};

/** Whether `key` should be shown for the step given what is typed so far (no key for a local AI). */
export function fieldShown(key: string, drafts: Record<string, string>, settings: SettingsView): boolean {
  if (key !== "RECALL_LLM_API_KEY") return true;
  const provider = (drafts.RECALL_LLM_PROVIDER ?? settings.values.RECALL_LLM_PROVIDER ?? "").trim();
  return !LOCAL_PROVIDERS.has(provider);
}

/**
 * The `save_settings` arguments for what was typed into one step: every
 * other saved value is kept (saving replaces all values), secrets go
 * separately, and empty secret drafts leave the saved secret alone.
 */
export function stepSave(
  settings: SettingsView,
  drafts: Record<string, string>,
): { values: Record<string, string>; secrets: Record<string, string> } {
  const secretKeys = new Set(settings.fields.filter((field) => field.kind === "secret").map((field) => field.key));
  const values = { ...settings.values };
  const secrets: Record<string, string> = {};
  for (const [key, raw] of Object.entries(drafts)) {
    const value = raw.trim();
    if (secretKeys.has(key)) {
      if (value !== "") secrets[key] = value;
    } else {
      values[key] = value;
    }
  }
  return { values, secrets };
}
