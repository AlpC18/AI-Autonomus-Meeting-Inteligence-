// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

// Clicking the toolbar button starts or stops sending the current tab's call
// audio to the engine (ws://127.0.0.1:8766). Audio from other tabs is dropped.

const ENGINE = "ws://127.0.0.1:8766";
const RECONNECT_MS = 2000;

let capturedTab = null;
let socket = null;
let retry = null;

async function show(text, color, title) {
  await browser.action.setBadgeText({ text });
  await browser.action.setBadgeBackgroundColor({ color });
  await browser.action.setTitle({ title });
}

function connect() {
  socket = new WebSocket(ENGINE);
  socket.binaryType = "arraybuffer";
  socket.addEventListener("open", () => void show("ON", "#15803d", "Continuum hears this call. Click to stop."));
  socket.addEventListener("close", (event) => {
    socket = null;
    if (capturedTab === null) return;
    void show(event.code === 1008 ? "!" : "…", event.code === 1008 ? "#b91c1c" : "#a16207",
      event.code === 1008 ? "Continuum is already capturing another tab." : "Waiting for the Continuum app.");
    retry = setTimeout(connect, RECONNECT_MS);
  });
}

function stop() {
  capturedTab = null;
  clearTimeout(retry);
  socket?.close();
  socket = null;
  void show("", "#000000", "Continuum: capture this call's audio");
}

/** Starts or stops capturing `tab` (what clicking the toolbar button does). */
function toggle(tab) {
  if (capturedTab !== null) {
    stop();
    return;
  }
  capturedTab = tab.id;
  void show("…", "#a16207", "Waiting for the Continuum app.");
  connect();
}

browser.action.onClicked.addListener(toggle);
browser.tabs.onRemoved.addListener((tabId) => {
  if (tabId === capturedTab) stop();
});
browser.runtime.onMessage.addListener((message, sender) => {
  if (message?.type !== "audio" || sender.tab?.id !== capturedTab || socket?.readyState !== WebSocket.OPEN) return;
  socket.send(Float32Array.from(message.samples).buffer);
});
