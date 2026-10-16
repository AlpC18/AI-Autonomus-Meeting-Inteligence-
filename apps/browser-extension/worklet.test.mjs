// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

// Run with: node --test apps/browser-extension
import assert from "node:assert/strict";
import { test } from "node:test";
import { downsampler } from "./worklet.js";

for (const rate of [48000, 44100, 16000]) {
  test(`one second at ${rate} Hz becomes ten 100 ms blocks at 16 kHz`, () => {
    const blocks = [];
    const feed = downsampler(rate, (block) => blocks.push(block));
    const second = Float32Array.from({ length: rate }, (_, i) => Math.sin((2 * Math.PI * 440 * i) / rate));
    for (let i = 0; i < rate; i += 128) feed(second.subarray(i, i + 128)); // render quanta
    assert.equal(blocks.length, 10);
    assert.ok(blocks.every((block) => block.length === 1600));
  });
}

test("a constant level is kept", () => {
  const blocks = [];
  downsampler(48000, (block) => blocks.push(block))(new Float32Array(4800).fill(0.25));
  assert.ok(blocks[0].every((sample) => Math.abs(sample - 0.25) < 1e-6));
});
