// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState, type FormEvent } from "react";
import { speakerTurns } from "./speakerTurns";
import { displaySpeaker, speakerColor } from "./speakers";
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
 * The people in the meeting: everyone heard so far, in their transcript
 * colour, each with a box for their real name. The engine applies a name to
 * everything said from then on, and the transcript on screen is relabelled.
 * When remote voices are not told apart, says how to turn that on.
 */
export function SpeakerNamer({ segments, connected, send }: SpeakerNamerProps) {
  const speakers = speakersIn(segments);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const separated = speakers.some((label) => /^Speaker \d+$/.test(label));

  const save = (event: FormEvent, label: string) => {
    event.preventDefault();
    const name = drafts[label] ?? "";
    const problem = nameProblem(name);
    if (problem) {
      setMessage(problem);
      return;
    }
    const to = name.trim().replace(/\s+/g, " ");
    if (send({ type: "rename_speaker", from: label, to })) {
      setMessage(t("{from} will be shown as {to}.", { from: displaySpeaker(label), to }));
      setDrafts((current) => ({ ...current, [label]: "" }));
    } else {
      setMessage(t("The engine is not connected; try again in a moment."));
    }
  };

  return (
    <section aria-label={t("People")} className="rounded-xl border border-zinc-200 bg-surface p-4">
      <h2 className="text-sm font-semibold">{t("People")}</h2>
      {speakers.length === 0 ? (
        <p className="mt-2 text-sm text-zinc-500">{t("People appear here as they speak.")}</p>
      ) : (
        <ul className="mt-3 space-y-2.5">
          {speakers.map((label) => (
            <li key={label}>
              <form onSubmit={(event) => save(event, label)} className="flex items-center gap-2">
                <span className={`w-20 shrink-0 truncate text-sm font-semibold ${speakerColor(label)}`}>{displaySpeaker(label)}</span>
                <input
                  aria-label={t("Name for {person}", { person: displaySpeaker(label) })}
                  value={drafts[label] ?? ""}
                  maxLength={MAX_NAME_LENGTH}
                  onChange={(event) => setDrafts((current) => ({ ...current, [label]: event.target.value }))}
                  placeholder={t("e.g. Ana")}
                  className="min-w-0 flex-1 rounded-md border border-zinc-300 px-2 py-1 text-sm"
                />
                <button
                  type="submit"
                  disabled={!connected}
                  aria-label={t("Save name for {person}", { person: displaySpeaker(label) })}
                  className="cursor-pointer rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t("Save")}
                </button>
              </form>
            </li>
          ))}
        </ul>
      )}
      {!separated && speakers.includes("others") && (
        <p className="mt-3 text-xs leading-relaxed text-zinc-600">
          {t("Everyone else is heard as one voice. To tell them apart as Person 1, Person 2, …, add a free Hugging Face token in Get started.")}
        </p>
      )}
      {message && (
        <p role="status" className="mt-2 text-xs text-zinc-700">
          {message}
        </p>
      )}
    </section>
  );
}
