// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useEffect, useState, type FormEvent } from "react";
import { invoke } from "@tauri-apps/api/core";
import { canConnectGoogle, changedSecrets, connectionLines, groupFields, parseSettings, type SettingField, type SettingsView } from "./settings";
import { t } from "../i18n";

const INPUT = "mt-1 w-full rounded-md border border-zinc-300 p-1.5 text-sm text-zinc-900";

/**
 * Settings screen. Ordinary values are saved to a private file and secrets
 * to the macOS Keychain; a saved secret is never shown again, only whether it
 * is set. Saving checks the whole configuration and restarts the engine.
 */
export function SettingsPanel() {
  const [view, setView] = useState<SettingsView | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [secretDrafts, setSecretDrafts] = useState<Record<string, string>>({});
  const [cleared, setCleared] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<string[]>([]);

  const load = () => {
    invoke<unknown>("get_settings")
      .then((reply) => {
        const parsed = parseSettings(reply);
        setView(parsed);
        setValues(parsed?.values ?? {});
        setSecretDrafts({});
        setCleared(new Set());
      })
      .catch((cause: unknown) => setMessages([String(cause)]));
  };
  useEffect(load, []);

  const save = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setMessages([t("Saving and restarting the engine…")]);
    invoke<string[]>("save_settings", { values, secrets: changedSecrets(secretDrafts, cleared) })
      .then((problems) => {
        setMessages(problems.length === 0 ? [t("Saved. The engine restarted with the new settings.")] : problems);
        load();
      })
      .catch((cause: unknown) => setMessages([String(cause)]))
      .finally(() => setBusy(false));
  };

  const connectGoogle = () => {
    setBusy(true);
    setMessages([t("Finish signing in to Google in your browser…")]);
    invoke<string>("google_connect")
      .then((message) => {
        setMessages([message]);
        load();
      })
      .catch((cause: unknown) => setMessages([String(cause)]))
      .finally(() => setBusy(false));
  };

  const testConnections = () => {
    setBusy(true);
    setMessages([t("Testing the saved connections…")]);
    invoke<unknown>("check_connections")
      .then((reply) => setMessages(connectionLines(reply)))
      .catch((cause: unknown) => setMessages([String(cause)]))
      .finally(() => setBusy(false));
  };

  if (!view) return <p className="mt-4 text-sm text-zinc-600">{messages[0] ?? t("Loading settings…")}</p>;

  const input = (field: SettingField) => {
    const id = `setting-${field.key}`;
    const value = values[field.key] ?? "";
    const set = (next: string) => setValues((current) => ({ ...current, [field.key]: next }));
    if (field.kind === "secret") {
      const saved = view.secretsSet.includes(field.key) && !cleared.has(field.key);
      return (
        <div className="mt-1 flex gap-2">
          <input
            id={id}
            type="password"
            autoComplete="off"
            value={secretDrafts[field.key] ?? ""}
            placeholder={saved ? t("Saved in Keychain — type to replace") : t("Not set")}
            onChange={(event) => setSecretDrafts((current) => ({ ...current, [field.key]: event.target.value }))}
            className={INPUT.replace("mt-1 ", "")}
          />
          {saved && (
            <button
              type="button"
              onClick={() => setCleared((current) => new Set(current).add(field.key))}
              className="cursor-pointer rounded-md border border-zinc-400 px-2 text-xs hover:bg-zinc-100"
            >
              {t("Remove")}
            </button>
          )}
        </div>
      );
    }
    if (field.kind === "toggle") {
      return (
        <input
          id={id}
          type="checkbox"
          checked={(value || field.options[0]) === "1"}
          onChange={(event) => set(event.target.checked ? "1" : "0")}
          className="mt-1 h-4 w-4"
        />
      );
    }
    if (field.kind === "choice") {
      return (
        <select id={id} value={value || field.options[0]} onChange={(event) => set(event.target.value)} className={INPUT}>
          {field.options.map((option) => (
            <option key={option} value={option}>
              {option || t("None")}
            </option>
          ))}
        </select>
      );
    }
    return (
      <input
        id={id}
        inputMode={field.kind === "number" ? "numeric" : undefined}
        value={value}
        maxLength={2000}
        onChange={(event) => set(event.target.value)}
        className={INPUT}
      />
    );
  };

  return (
    <form onSubmit={save} aria-label={t("Settings")} className="mt-4 flex flex-col gap-6">
      {groupFields(view.fields).map(([group, fields]) => (
        <fieldset key={group} className="rounded-lg border border-zinc-300 p-3">
          <legend className="px-1 font-semibold">{t(group)}</legend>
          <div className="grid gap-3 md:grid-cols-2">
            {fields.map((field) => (
              <div key={field.key}>
                <label htmlFor={`setting-${field.key}`} className="text-sm font-medium">
                  {t(field.label)}
                </label>
                {input(field)}
                {field.help && <p className="mt-0.5 text-xs text-zinc-600">{t(field.help)}</p>}
                {field.key === "GOOGLE_REFRESH_TOKEN" && (
                  <button
                    type="button"
                    disabled={busy || !canConnectGoogle(view)}
                    onClick={connectGoogle}
                    title={canConnectGoogle(view) ? undefined : t("Save the Google client ID and secret first.")}
                    className="mt-1 cursor-pointer rounded-md border border-zinc-400 px-2 py-1 text-xs hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {t("Connect Google…")}
                  </button>
                )}
              </div>
            ))}
          </div>
        </fieldset>
      ))}
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={busy}
          className="cursor-pointer rounded-md bg-zinc-900 px-3 py-1.5 text-sm text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? t("Working…") : t("Save and restart engine")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={testConnections}
          title={t("Signs in to each saved integration and asks the AI provider for a one-word reply.")}
          className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {t("Test connections")}
        </button>
      </div>
      {messages.length > 0 && (
        <ul role="status" className="text-sm text-zinc-700">
          {messages.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
    </form>
  );
}
