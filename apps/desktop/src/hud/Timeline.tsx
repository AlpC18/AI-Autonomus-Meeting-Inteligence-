// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import type { Topic } from "./transcriptStream";
import { language, t } from "../i18n";

/** "14:05" in the user's own time zone (or "2:05 PM", as the interface language writes it). */
export function timeOf(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString(language() === "tr" ? "tr-TR" : "en-GB", { hour: "2-digit", minute: "2-digit" });
}

interface TimelineProps {
  topics: readonly Topic[];
}

/** What the meeting talked about, and from what time; the engine adds an entry every two minutes of talk. */
export function Timeline({ topics }: TimelineProps) {
  return (
    <section aria-label={t("Timeline")} className="rounded-xl border border-zinc-200 bg-surface p-4">
      <h2 className="text-sm font-semibold">{t("Timeline")}</h2>
      {topics.length === 0 ? (
        <p className="mt-2 text-sm text-zinc-500">{t("Topics appear here every two minutes of conversation.")}</p>
      ) : (
        <ol className="relative mt-3 space-y-3 border-l border-zinc-200 pl-4">
          {topics.map((topic, index) => (
            <li key={`${topic.at}-${index}`} className="relative">
              <span aria-hidden="true" className="absolute top-1.5 -left-[1.3rem] size-2 rounded-full bg-accent" />
              <time dateTime={topic.at} className="block text-xs font-medium text-zinc-500 tabular-nums">
                {timeOf(topic.at)}
              </time>
              <p className="text-sm leading-snug text-zinc-900">{topic.title}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
