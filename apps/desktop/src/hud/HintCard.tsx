// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import type { Hint } from "./hints";

const LABELS: Record<Hint["kind"], string> = {
  code: "Code context",
  commitment: "Commitment risk",
  hesitation: "Hesitation",
};

/** One live hint in the overlay, styled like a fact-check card but in sky blue. */
export function HintCard({ hint, onDismiss }: { hint: Hint; onDismiss: () => void }) {
  return (
    <article
      role="status"
      aria-live="polite"
      className="rounded-xl border border-white/15 bg-zinc-900/95 p-3 text-zinc-100 shadow-lg motion-safe:animate-[fade-in_150ms_ease-out]"
    >
      <header className="flex items-center gap-2">
        <h2 className="grow text-xs font-semibold uppercase tracking-wide text-sky-300">{LABELS[hint.kind]}</h2>
        <button
          type="button"
          onClick={onDismiss}
          aria-label={`Dismiss ${LABELS[hint.kind].toLowerCase()}`}
          className="-m-1 grid size-8 cursor-pointer place-items-center rounded-md text-zinc-400 hover:bg-white/10 hover:text-zinc-100 focus-visible:outline-2 focus-visible:outline-sky-300"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 stroke-current" strokeWidth="2">
            <path d="M5 5l10 10M15 5 5 15" />
          </svg>
        </button>
      </header>
      <p className="mt-1 text-sm font-semibold">{hint.title}</p>
      <p className="mt-1 text-sm text-zinc-300">{hint.body}</p>
      {hint.details.length > 0 && (
        <ul className="mt-2 space-y-0.5 font-mono text-xs text-zinc-300">
          {hint.details.map((line) => (
            <li key={line} className="truncate" title={line}>
              {line}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
