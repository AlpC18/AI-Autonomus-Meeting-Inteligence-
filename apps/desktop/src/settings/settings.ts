// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

/** How a setting is edited. */
export type FieldKind = "text" | "number" | "toggle" | "choice" | "secret";

/** One setting, as described by the desktop backend. */
export interface SettingField {
  key: string;
  label: string;
  group: string;
  kind: FieldKind;
  options: string[];
  help: string;
}

/** What the settings screen shows. Secret values are never included. */
export interface SettingsView {
  fields: SettingField[];
  values: Record<string, string>;
  /** Keys of secrets stored in the Keychain. */
  secretsSet: string[];
}

const KINDS: readonly FieldKind[] = ["text", "number", "toggle", "choice", "secret"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

/** Reads a `get_settings` reply, or returns `null` if it is malformed. */
export function parseSettings(reply: unknown): SettingsView | null {
  if (!isRecord(reply) || !Array.isArray(reply.fields) || !isRecord(reply.values) || !isStringArray(reply.secretsSet)) {
    return null;
  }
  const fields = reply.fields.flatMap((field): SettingField[] =>
    isRecord(field) &&
    typeof field.key === "string" &&
    typeof field.label === "string" &&
    typeof field.group === "string" &&
    typeof field.help === "string" &&
    KINDS.includes(field.kind as FieldKind) &&
    isStringArray(field.options)
      ? [{ ...field, kind: field.kind as FieldKind, options: field.options } as SettingField]
      : [],
  );
  const values = Object.fromEntries(
    Object.entries(reply.values).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
  );
  return { fields, values, secretsSet: reply.secretsSet };
}

/** Fields grouped by their group name, in first-seen order. */
export function groupFields(fields: readonly SettingField[]): [string, SettingField[]][] {
  const groups = new Map<string, SettingField[]>();
  for (const field of fields) groups.set(field.group, [...(groups.get(field.group) ?? []), field]);
  return [...groups];
}

/** Whether Google can be connected: its client ID and secret are saved (the sign-in uses saved settings). */
export function canConnectGoogle(view: SettingsView): boolean {
  return Boolean(view.values.GOOGLE_CLIENT_ID?.trim()) && view.secretsSet.includes("GOOGLE_CLIENT_SECRET");
}

/**
 * The secrets to send on save: only those the user typed into or asked to
 * clear. Untouched secrets are left out, so they stay as they are.
 */
export function changedSecrets(drafts: Record<string, string>, cleared: ReadonlySet<string>): Record<string, string> {
  const changed: Record<string, string> = {};
  for (const [key, value] of Object.entries(drafts)) if (value.trim() !== "") changed[key] = value.trim();
  for (const key of cleared) changed[key] = "";
  return changed;
}
