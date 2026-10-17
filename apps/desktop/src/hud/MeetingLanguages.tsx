// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { SettingsView } from "../settings/settings";
import { stepSave } from "../setup/setup";
import { t } from "../i18n";

export const SETTING = "RECALL_MEETING_LANGUAGES";

/** Languages offered, by Whisper code, each named in its own language. */
export const LANGUAGES: readonly (readonly [string, string])[] = [
  ["en", "English"], ["tr", "Türkçe"], ["de", "Deutsch"], ["it", "Italiano"], ["sq", "Shqip"],
  ["fr", "Français"], ["es", "Español"], ["pt", "Português"], ["nl", "Nederlands"], ["pl", "Polski"],
  ["ru", "Русский"], ["ar", "العربية"], ["el", "Ελληνικά"], ["bs", "Bosanski"], ["sr", "Srpski"],
];  // prettier-ignore

/** The codes in a saved value such as "en,tr,sq". */
export function codesOf(value: string | undefined): string[] {
  return (value ?? "").split(",").map((code) => code.trim().toLowerCase()).filter(Boolean);
}

interface MeetingLanguagesProps {
  settings: SettingsView | null;
  saved: () => void;
}

/**
 * The languages spoken in the meeting. Recall then writes speech only in one
 * of them, never in another alphabet. Saving restarts the engine.
 */
export function MeetingLanguages({ settings, saved }: MeetingLanguagesProps) {
  const current = codesOf(settings?.values[SETTING]);
  const [chosen, setChosen] = useState<string[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const selected = chosen ?? current;
  const changed = chosen !== null && chosen.join(",") !== current.join(",");

  const toggle = (code: string) =>
    setChosen(selected.includes(code) ? selected.filter((c) => c !== code) : [...selected, code]);

  const save = () => {
    if (!settings) return;
    setBusy(true);
    invoke<string[]>("save_settings", stepSave(settings, { [SETTING]: selected.join(",") }))
      .then((problems) => {
        setMessage(problems.length > 0 ? problems.join(" ") : t("Saved. Live captions now stay in these languages."));
        setChosen(null);
        saved();
      })
      .catch((error: unknown) => setMessage(String(error)))
      .finally(() => setBusy(false));
  };

  return (
    <section aria-label={t("Meeting languages")} className="rounded-xl border border-zinc-200 bg-surface p-4">
      <h2 className="text-sm font-semibold">{t("Meeting languages")}</h2>
      <p className="mt-1 text-xs leading-relaxed text-zinc-600">
        {selected.length === 0
          ? t("Any language. Pick the ones spoken here, so nothing is written in another alphabet.")
          : t("Speech is written only in these languages.")}
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {LANGUAGES.map(([code, name]) => (
          <button
            key={code}
            type="button"
            aria-pressed={selected.includes(code)}
            onClick={() => toggle(code)}
            className="cursor-pointer rounded-full border border-zinc-300 px-2.5 py-0.5 text-xs hover:bg-zinc-100 aria-pressed:border-accent aria-pressed:bg-accent-soft aria-pressed:font-medium"
          >
            {name}
          </button>
        ))}
      </div>
      {changed && (
        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            disabled={busy || !settings}
            onClick={save}
            className="cursor-pointer rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90 disabled:opacity-50"
          >
            {busy ? t("Working…") : t("Save languages")}
          </button>
          <span className="text-xs text-zinc-500">{t("Restarts the engine: set this before the meeting.")}</span>
        </div>
      )}
      {message && (
        <p role="status" className="mt-2 text-xs text-zinc-700">
          {message}
        </p>
      )}
    </section>
  );
}
