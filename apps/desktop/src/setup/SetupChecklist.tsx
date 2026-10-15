// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { openUrl } from "@tauri-apps/plugin-opener";
import { PRIVACY_PANES, type SetupStep } from "./setup";

interface SetupProps {
  steps: SetupStep[];
  openSettings: () => void;
  dismiss: () => void;
}

/** First-run checklist: what to set up before the first meeting, with shortcuts. */
export function SetupChecklist({ steps, openSettings, dismiss }: SetupProps) {
  return (
    <section aria-label="Get started" className="mt-4 max-w-2xl">
      <h2 className="text-lg font-semibold">Get started</h2>
      <ol className="mt-2 flex flex-col gap-3">
        {steps.map((step) => (
          <li key={step.id} className="rounded-md border border-zinc-200 p-3">
            <p className="font-medium">
              <span aria-label={step.done ? "Done" : "To do"}>{step.done ? "✓" : "○"}</span> {step.title}
            </p>
            <p className="mt-1 text-sm text-zinc-700">{step.help}</p>
            {step.id === "permissions" ? (
              <div className="mt-2 flex gap-2">
                {Object.entries(PRIVACY_PANES).map(([name, url]) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() => void openUrl(url).catch(() => undefined)}
                    className="cursor-pointer rounded-md border border-zinc-400 px-2 py-1 text-xs hover:bg-zinc-100"
                  >
                    Open {name} settings
                  </button>
                ))}
              </div>
            ) : (
              !step.done && (
                <button
                  type="button"
                  onClick={openSettings}
                  className="mt-2 cursor-pointer rounded-md border border-zinc-400 px-2 py-1 text-xs hover:bg-zinc-100"
                >
                  Open Settings
                </button>
              )
            )}
          </li>
        ))}
      </ol>
      <button type="button" onClick={dismiss} className="mt-3 cursor-pointer text-sm text-zinc-600 underline">
        Hide this checklist
      </button>
    </section>
  );
}
