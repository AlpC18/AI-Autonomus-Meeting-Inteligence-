// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState, type FormEvent } from "react";
import type { Answer, EngineCommand } from "./transcriptStream";
import { t } from "../i18n";

/** Longest question the engine accepts. */
export const MAX_QUESTION_LENGTH = 500;

interface AskPanelProps {
  connected: boolean;
  send: (message: EngineCommand) => boolean;
  answers: Readonly<Record<string, Answer>>;
}

let nextQuestion = 0;

/**
 * "Ask your meetings": a question is answered by the configured AI model from
 * what was said in past meetings, with the quotes it relied on.
 */
export function AskPanel({ connected, send, answers }: AskPanelProps) {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState<{ id: string; question: string } | null>(null);
  const answer = asked ? answers[asked.id] : undefined;

  const ask = (event: FormEvent) => {
    event.preventDefault();
    const text = question.trim();
    if (!text) return;
    const id = `q${Date.now()}-${nextQuestion++}`;
    if (send({ type: "ask", id, question: text })) setAsked({ id, question: text });
  };

  return (
    <section aria-label={t("Ask your meetings")} className="mt-6">
      <h2 className="text-lg font-semibold">{t("Ask your meetings")}</h2>
      <form onSubmit={ask} className="mt-2 flex gap-2">
        <input
          aria-label={t("Question")}
          value={question}
          maxLength={MAX_QUESTION_LENGTH}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={t("e.g. What did we decide about the budget?")}
          className="min-w-0 flex-1 rounded-md border border-zinc-300 p-1.5 text-sm"
        />
        <button
          type="submit"
          disabled={!connected || question.trim() === ""}
          className="cursor-pointer rounded-md bg-zinc-900 px-3 py-1.5 text-sm text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {t("Ask")}
        </button>
      </form>
      {asked && !answer && <p className="mt-2 text-sm text-zinc-600">{t("Looking through your meetings…")}</p>}
      {answer && <AnswerView answer={answer} />}
    </section>
  );
}

/** An answer or brief from memory, with the numbered statements it cites. */
export function AnswerView({ answer }: { answer: Answer }) {
  return (
    <div role="status" className="mt-2 text-sm">
      {answer.error ? (
        <p className="text-red-700">{answer.error}</p>
      ) : (
        <>
          <p className="whitespace-pre-wrap">{answer.text}</p>
          {answer.sources.length > 0 && (
            <ol className="mt-2 flex flex-col gap-1 text-xs text-zinc-700">
              {answer.sources.map((source) => (
                <li key={source.number}>
                  [{source.number}] {source.spokenAt.toLocaleString()} · <strong>{source.speaker}</strong>
                  {source.disputed ? ` (${t("disputed")})` : ""}: “{source.text}”
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </div>
  );
}
