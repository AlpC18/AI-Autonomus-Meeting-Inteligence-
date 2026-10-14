// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState, type FormEvent, type KeyboardEvent } from "react";
import type { EngineCommand } from "../hud/transcriptStream";

/** Longest note the engine accepts, in characters. */
export const MAX_NOTE_LENGTH = 2000;

interface NotepadProps {
  /** Whether the engine is connected; notes cannot be added otherwise. */
  connected: boolean;
  /** Sends a command to the engine; returns `false` if it could not be sent. */
  send: (message: EngineCommand) => boolean;
}

/**
 * Notepad for the live meeting.
 *
 * Each note is added to the transcript at the moment it is written, so it
 * sits next to what was being said, and the AI summary treats notes as the
 * user's priorities. Enter adds the note; Shift+Enter starts a new line.
 */
export function Notepad({ connected, send }: NotepadProps) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const add = () => {
    const text = draft.trim();
    if (!text) return;
    if (send({ type: "note", text })) {
      setDraft("");
      setError(null);
    } else {
      setError("The engine is not connected; your note was kept here and not added yet.");
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    add();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      add();
    }
  };

  return (
    <section aria-label="Notes" className="mt-6">
      <h2 className="text-lg font-semibold">Notes</h2>
      <form onSubmit={onSubmit} className="mt-2 flex flex-col gap-2">
        <label htmlFor="meeting-note" className="text-sm text-zinc-600">
          Write what matters to you. It is added to the transcript at this moment.
        </label>
        <textarea
          id="meeting-note"
          value={draft}
          maxLength={MAX_NOTE_LENGTH}
          rows={3}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="e.g. Push back on the December date"
          className="rounded-md border border-zinc-300 p-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900"
        />
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={!connected || draft.trim() === ""}
            className="cursor-pointer rounded-md bg-zinc-900 px-3 py-1.5 text-sm text-white hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Add note
          </button>
          {!connected && <span className="text-xs text-zinc-600">Waiting for the engine…</span>}
        </div>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
      </form>
    </section>
  );
}
