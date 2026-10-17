// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState, type FormEvent } from "react";
import { speakerTurns } from "./speakerTurns";
import type { EngineCommand, TranscriptSegment } from "./transcriptStream";
import { t } from "../i18n";

/** Speaker of typed notes; it cannot be renamed. */
const NOTE_SPEAKER = "Note";

/** Longest speaker name the engine accepts. */
export const MAX_NAME_LENGTH = 40;

/** Characters the engine refuses in names (they would break the Markdown notes). */
const FORBIDDEN = /[*`_[\]<>|#\\]/;

/** Every speaker heard so far, in order of first appearance, without the note speaker. */
export function speakersIn(segments: readonly TranscriptSegment[]): string[] {
  const seen = new Set<string>();
  for (const segment of segments) {
    for (const turn of speakerTurns(segment)) {
      if (turn.speaker !== NOTE_SPEAKER) seen.add(turn.speaker);
    }
  }
  return [...seen];
}

/** Why `name` cannot be used, or `null` when it is fine. */
export function nameProblem(name: string): string | null {
  const trimmed = name.trim();
  if (trimmed === "") return t("Type a name.");
  if (trimmed.length > MAX_NAME_LENGTH) return t("Use at most {count} characters.", { count: MAX_NAME_LENGTH });
  if (FORBIDDEN.test(trimmed)) return t("Leave out * ` _ [ ] < > | # and \\.");
  if (trimmed.toLowerCase() === NOTE_SPEAKER.toLowerCase()) return t("\"{name}\" is reserved.", { name: NOTE_SPEAKER });
  return null;
}

interface SpeakerNamerProps {
  segments: readonly TranscriptSegment[];
  connected: boolean;
  send: (message: EngineCommand) => boolean;
}

/**
 * Lets the user give real names to "Speaker 1", "Speaker 2", ... (and to "me").
 *
 * The engine applies a name to everything said from then on and confirms it,
 * and the transcript already on screen is relabelled at the same time.
 */
export function SpeakerNamer({ segments, connected, send }: SpeakerNamerProps) {
  const speakers = speakersIn(segments);
  const [speaker, setSpeaker] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const chosen = speakers.includes(speaker) ? speaker : (speakers[0] ?? "");

  if (speakers.length === 0) return null;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const problem = nameProblem(name);
    if (problem) {
      setMessage(problem);
      return;
    }
    const to = name.trim().replace(/\s+/g, " ");
    if (send({ type: "rename_speaker", from: chosen, to })) {
      setMessage(t("{from} will be shown as {to}.", { from: chosen, to }));
      setName("");
      setSpeaker(to);
    } else {
      setMessage(t("The engine is not connected; try again in a moment."));
    }
  };

  return (
    <form onSubmit={onSubmit} aria-label={t("Name a speaker")} className="mt-3 flex flex-wrap items-end gap-2">
      <label className="flex flex-col text-xs text-zinc-600">
        {t("Speaker")}
        <select
          value={chosen}
          onChange={(event) => setSpeaker(event.target.value)}
          className="mt-1 rounded-md border border-zinc-300 p-1.5 text-sm text-zinc-900"
        >
          {speakers.map((label) => (
            <option key={label} value={label}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col text-xs text-zinc-600">
        {t("Real name")}
        <input
          value={name}
          maxLength={MAX_NAME_LENGTH}
          onChange={(event) => setName(event.target.value)}
          placeholder={t("e.g. Ana")}
          className="mt-1 rounded-md border border-zinc-300 p-1.5 text-sm text-zinc-900"
        />
      </label>
      <button
        type="submit"
        disabled={!connected}
        className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1.5 text-sm hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
      >
        {t("Rename")}
      </button>
      {message && (
        <p role="status" className="w-full text-xs text-zinc-700">
          {message}
        </p>
      )}
    </form>
  );
}
