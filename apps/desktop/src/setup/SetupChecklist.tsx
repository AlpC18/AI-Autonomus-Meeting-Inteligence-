// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { openUrl } from "@tauri-apps/plugin-opener";
import type { SettingField, SettingsView } from "../settings/settings";
import { PRIVACY_PANES, STEP_FIELDS, fieldShown, stepSave, type SetupStep } from "./setup";
import { t } from "../i18n";

interface SetupProps {
  steps: SetupStep[];
  settings: SettingsView;
  /** Called after a step was saved, so the settings (and the steps) are re-read. */
  saved: () => void;
  openSettings: () => void;
  dismiss: () => void;
}

const BUTTON = "cursor-pointer rounded-md border border-zinc-400 px-2 py-1 text-xs hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50";
const INPUT = "rounded-md border border-zinc-300 px-2 py-1 text-sm";

/** The inputs that finish one step, saved together with "Save". */
function StepForm({ step, settings, saved }: { step: SetupStep; settings: SettingsView; saved: () => void }) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fields = STEP_FIELDS[step.id]
    .map((key) => settings.fields.find((field) => field.key === key))
    .filter((field): field is SettingField => field !== undefined && fieldShown(field.key, drafts, settings));
  if (fields.length === 0) return null;

  const set = (key: string, value: string) => setDrafts((current) => ({ ...current, [key]: value }));
  const save = () => {
    setBusy(true);
    setMessage(t("Saving…"));
    invoke<string[]>("save_settings", stepSave(settings, drafts))
      .then((problems) => {
        setMessage(problems.length > 0 ? problems.join(" ") : null);
        setDrafts({});
        saved();
      })
      .catch((cause: unknown) => setMessage(String(cause)))
      .finally(() => setBusy(false));
  };

  return (
    <div className="mt-2 flex flex-col gap-2">
      {fields.map((field) => {
        const value = drafts[field.key] ?? (field.kind === "secret" ? "" : (settings.values[field.key] ?? ""));
        return (
          <label key={field.key} className="flex items-center gap-2 text-sm">
            <span className="w-40 shrink-0 text-zinc-700">{t(field.label)}</span>
            {field.kind === "choice" ? (
              <select value={value} onChange={(event) => set(field.key, event.target.value)} className={INPUT}>
                {field.options.map((option) => (
                  <option key={option} value={option}>
                    {option || t("(choose)")}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={field.kind === "secret" ? "password" : "text"}
                autoComplete="off"
                value={value}
                placeholder={field.kind === "secret" && settings.secretsSet.includes(field.key) ? t("saved") : undefined}
                onChange={(event) => set(field.key, event.target.value)}
                className={`${INPUT} flex-1`}
              />
            )}
            {field.key === "RECALL_NOTES_DIR" && (
              <button
                type="button"
                className={BUTTON}
                onClick={() =>
                  void open({ directory: true, title: t("Choose the notes folder") })
                    .then((folder) => typeof folder === "string" && set(field.key, folder))
                    .catch(() => undefined)
                }
              >
                {t("Choose…")}
              </button>
            )}
          </label>
        );
      })}
      <div className="flex items-center gap-2">
        <button type="button" disabled={busy || Object.keys(drafts).length === 0} onClick={save} className={BUTTON}>
          {t("Save")}
        </button>
        {message && (
          <span role="status" className="text-xs text-zinc-700">
            {message}
          </span>
        )}
      </div>
    </div>
  );
}

/** First-run checklist: each step can be finished right here, or in Settings. */
export function SetupChecklist({ steps, settings, saved, openSettings, dismiss }: SetupProps) {
  return (
    <section aria-label={t("Get started")} className="mt-4 max-w-2xl">
      <h2 className="text-lg font-semibold">{t("Get started")}</h2>
      <ol className="mt-2 flex flex-col gap-3">
        {steps.map((step) => (
          <li key={step.id} className="rounded-xl border border-zinc-200 bg-surface p-5">
            <p className="font-medium">
              <span aria-label={step.done ? t("Done") : t("To do")} className={step.done ? "text-accent" : "text-zinc-500"}>{step.done ? "✓" : "○"}</span> {t(step.title)}
            </p>
            <p className="mt-1 text-sm text-zinc-700">{t(step.help)}</p>
            {step.id === "permissions" ? (
              <div className="mt-2 flex gap-2">
                {Object.entries(PRIVACY_PANES).map(([name, url]) => (
                  <button key={name} type="button" onClick={() => void openUrl(url).catch(() => undefined)} className={BUTTON}>
                    {t("Open {name} settings", { name: t(name) })}
                  </button>
                ))}
              </div>
            ) : (
              !step.done && <StepForm step={step} settings={settings} saved={saved} />
            )}
          </li>
        ))}
      </ol>
      <div className="mt-3 flex gap-4 text-sm text-zinc-600">
        <button type="button" onClick={openSettings} className="cursor-pointer underline">
          {t("All settings")}
        </button>
        <button type="button" onClick={dismiss} className="cursor-pointer underline">
          {t("Hide this checklist")}
        </button>
      </div>
    </section>
  );
}
