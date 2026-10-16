// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

// Passes the call audio from tap.js to the background page, which sends it
// to the engine only while capture is on for this tab.
window.addEventListener("message", (event) => {
  if (event.source !== window || event.data?.type !== "continuum-call-audio" || !Array.isArray(event.data.samples)) return;
  browser.runtime.sendMessage({ type: "audio", samples: event.data.samples }).catch(() => undefined);
});
