// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

// Mixes the tab to mono, averages it down to 16 kHz (what the engine's
// speech model expects) and posts 100 ms blocks to the offscreen page.

const TARGET_RATE = 16000;
const BLOCK = TARGET_RATE / 10;

/** Returns a function that takes mono samples at `rate` and calls `emit` with each full block. */
export function downsampler(rate, emit) {
  let block = new Float32Array(BLOCK);
  let filled = 0;
  let sum = 0;
  let count = 0;
  // Integer bookkeeping: one output sample per `rate` units, 16000 units per input sample.
  let units = 0;
  return (samples) => {
    for (const sample of samples) {
      sum += sample;
      count += 1;
      units += TARGET_RATE;
      if (units >= rate) {
        units -= rate;
        block[filled++] = sum / count;
        sum = 0;
        count = 0;
        if (filled === BLOCK) {
          emit(block);
          block = new Float32Array(BLOCK);
          filled = 0;
        }
      }
    }
  };
}

if (typeof AudioWorkletProcessor !== "undefined") {
  class RecallBlocks extends AudioWorkletProcessor {
    constructor() {
      super();
      this.feed = downsampler(sampleRate, (block) => this.port.postMessage(block.buffer, [block.buffer]));
    }

    process(inputs) {
      const channels = inputs[0];
      if (!channels || channels.length === 0) return true;
      const mono = new Float32Array(channels[0].length);
      for (const channel of channels) for (let i = 0; i < mono.length; i++) mono[i] += channel[i] / channels.length;
      this.feed(mono);
      return true;
    }
  }
  registerProcessor("recall-blocks", RecallBlocks);
}
