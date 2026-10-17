// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { StreamStatus } from "./hud/transcriptStream";
import { t } from "./i18n";

interface EngineButtonProps {
  /** The engine connection: "open" means it is running and heard by the app. */
  status: StreamStatus;
}

/** Starts or stops the engine by hand; while stopped nothing is heard or recorded. */
export function EngineButton({ status }: EngineButtonProps) {
  const running = status === "open";
  // Which way the user asked to go, until the connection shows it happened.
  const [asked, setAsked] = useState<"start" | "stop" | null>(null);
  const [error, setError] = useState<string | null>(null);
  if ((asked === "start" && running) || (asked === "stop" && !running)) setAsked(null);

  const toggle = () => {
    setError(null);
    setAsked(running ? "stop" : "start");
    invoke(running ? "engine_stop" : "engine_start").catch((cause: unknown) => {
      setAsked(null);
      setError(String(cause));
    });
  };

  const label = asked === "start" ? t("Starting…") : asked === "stop" ? t("Stopping…") : running ? t("Stop engine") : t("Start engine");
  return (
    <span className="flex items-center gap-2">
      <button
        type="button"
        onClick={toggle}
        disabled={asked !== null}
        title={error ?? undefined}
        className={`cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium disabled:cursor-wait disabled:opacity-60 ${
          running ? "border border-zinc-300 hover:bg-zinc-100" : "bg-accent text-white hover:bg-accent/90"
        }`}
      >
        {label}
      </button>
      {error && (
        <span role="alert" className="max-w-48 truncate text-xs text-red-700">
          {error}
        </span>
      )}
    </span>
  );
}
