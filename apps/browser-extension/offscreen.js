// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

// Plays the captured tab back (capturing mutes it) and streams it to the
// engine as 100 ms blocks of 16 kHz mono float32 samples.

const ENGINE = "ws://127.0.0.1:8766";
const RECONNECT_MS = 2000;

const report = (type) => chrome.runtime.sendMessage({ target: "background", type });

async function start(streamId) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } },
  });
  stream.getAudioTracks()[0].addEventListener("ended", () => report("ended"));

  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  source.connect(context.destination); // so the user still hears the call
  await context.audioWorklet.addModule("worklet.js");
  const blocks = new AudioWorkletNode(context, "recall-blocks");
  source.connect(blocks);

  let socket = null;
  const connect = () => {
    socket = new WebSocket(ENGINE);
    socket.binaryType = "arraybuffer";
    socket.addEventListener("open", () => report("on"));
    socket.addEventListener("close", (event) => {
      report(event.code === 1008 ? "busy" : "waiting");
      setTimeout(connect, RECONNECT_MS);
    });
  };
  connect();
  blocks.port.onmessage = (event) => {
    if (socket?.readyState === WebSocket.OPEN) socket.send(event.data);
  };
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.target === "offscreen" && message.type === "start") {
    start(message.streamId).catch(() => report("ended"));
  }
});
