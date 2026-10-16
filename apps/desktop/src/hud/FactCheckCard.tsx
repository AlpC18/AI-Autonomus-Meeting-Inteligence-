// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import type { FactCheckAlert } from "./factCheck";

/** Props of {@link FactCheckCard}. */
export interface FactCheckCardProps {
  alert: FactCheckAlert;
  /** Called when the user closes the card. */
  onDismiss: () => void;
}

const DATE_FORMAT = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
});

function formatDate(date: Date): string {
  return Number.isNaN(date.getTime()) ? "earlier" : DATE_FORMAT.format(date);
}

/**
 * One fact-check alert: what was just said against what is on record, with
 * the source of the record. Announced politely to screen readers so it does
 * not interrupt, and the meaning never depends on colour alone.
 */
export function FactCheckCard({ alert, onDismiss }: FactCheckCardProps) {
  return (
    <article
      role="status"
      aria-live="polite"
      className="rounded-xl border border-white/15 bg-zinc-900/95 p-3 text-zinc-100 shadow-lg motion-safe:animate-[fade-in_150ms_ease-out]"
    >
      <header className="flex items-center gap-2">
        <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 shrink-0 fill-amber-400">
          <path d="M10 1.5 19 17.5H1L10 1.5Zm-1 6v5h2v-5H9Zm0 6.5v2h2v-2H9Z" />
        </svg>
        <h2 className="grow text-xs font-semibold uppercase tracking-wide text-amber-300">
          Fact check
        </h2>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss fact check"
          className="-m-1 grid size-8 cursor-pointer place-items-center rounded-md text-zinc-400 hover:bg-white/10 hover:text-zinc-100 focus-visible:outline-2 focus-visible:outline-amber-300"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 stroke-current" strokeWidth="2">
            <path d="M5 5l10 10M15 5 5 15" />
          </svg>
        </button>
      </header>

      {alert.claimed.length > 0 ? (
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="text-zinc-400">Said now</dt>
          <dd className="font-semibold">{alert.claimed.join(", ")}</dd>
          <dt className="text-zinc-400">On record</dt>
          <dd className="font-semibold text-amber-300">{alert.recorded.join(", ")}</dd>
        </dl>
      ) : (
        <div className="mt-2 text-sm">
          <p className="font-semibold">“{alert.statement}”</p>
          {alert.explanation && <p className="mt-1 text-amber-300">{alert.explanation}</p>}
        </div>
      )}

      <blockquote className="mt-2 border-l-2 border-white/20 pl-2 text-xs leading-relaxed text-zinc-300">
        “{alert.recordText}”
        <footer className="mt-0.5 text-zinc-400">
          {alert.recordSpeaker}, {formatDate(alert.recordSpokenAt)}
        </footer>
      </blockquote>
    </article>
  );
}
