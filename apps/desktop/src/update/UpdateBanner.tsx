// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

import { relaunch } from "@tauri-apps/plugin-process";
import { check, type Update } from "@tauri-apps/plugin-updater";
import { useEffect, useState } from "react";
import { t } from "../i18n";

/**
 * Offers a newer release once, at startup. The update is only installed when
 * the user clicks, and the updater refuses any file not signed with the
 * release key whose public half is in `tauri.conf.json`.
 */
export function UpdateBanner() {
  const [update, setUpdate] = useState<Update | null>(null);
  const [installing, setInstalling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // No release yet, offline, or a development build: there is simply nothing to offer.
    check()
      .then(setUpdate)
      .catch(() => setUpdate(null));
  }, []);

  if (!update) return null;

  const install = async () => {
    setInstalling(true);
    setError(null);
    try {
      await update.downloadAndInstall();
      await relaunch();
    } catch (cause: unknown) {
      setError(String(cause));
      setInstalling(false);
    }
  };

  return (
    <div role="status" className="mt-2 flex items-center gap-3 rounded-md bg-sky-50 p-2 text-sm">
      <span>{t("Continuum {version} is available.", { version: update.version })}</span>
      <button
        type="button"
        disabled={installing}
        onClick={() => void install()}
        className="cursor-pointer rounded-md border border-zinc-400 px-3 py-1 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {installing ? t("Installing…") : t("Install and restart")}
      </button>
      {error && <span className="text-red-700">{t("The update failed: {error}", { error })}</span>}
    </div>
  );
}
