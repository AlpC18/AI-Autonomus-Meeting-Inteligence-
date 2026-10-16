# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""End-to-end check of the live engine with real speech (macOS, no API keys).

A company document puts "the website budget is $35,000" in project memory.
The real engine is started; spoken audio (macOS ``say``) is streamed into it
the way the browser extension does, and someone says the budget is fifty
thousand dollars. The check passes when the transcript arrives, the fact
check flags $50,000 against $35,000, and ending the meeting writes notes.
With an AI provider set (CONTINUUM_LLM_PROVIDER and friends) it also needs
Turkish captions, the summary with its follow-up e-mail, and an answer to a
question about the meeting.

    uv run python scripts/live_meeting_check.py
"""

import asyncio
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from websockets.asyncio.client import connect

ENGINE_PORT, TAB_PORT = 8795, 8766  # the tab port is fixed; the extension expects it
ORIGIN = "chrome-extension://" + "a" * 32
RATE = 16000
SPEECH = (
    "Good morning everyone. Let's talk about the new website. "
    "I think the budget for the website is fifty thousand dollars. "
    "Ben will send the design review by Friday."
)
DOCUMENT = "# Website plan\n\nThe approved budget for the website is $35,000, agreed with finance in September.\n"


def spoken(text: str, folder: Path) -> np.ndarray:
    """``text`` read by macOS ``say``, as 16 kHz mono float32."""
    wav = folder / "speech.wav"
    subprocess.run(["say", "-o", str(wav), "--file-format=WAVE", f"--data-format=LEF32@{RATE}", text], check=True)
    data = wav.read_bytes()
    offset = 12
    while data[offset : offset + 4] != b"data":
        offset += 8 + struct.unpack("<I", data[offset + 4 : offset + 8])[0]
    return np.frombuffer(data[offset + 8 :], dtype="<f4")


async def wait_for(seen: dict[str, list[dict]], kind: str, seconds: float) -> None:
    for _ in range(int(seconds * 10)):
        if kind in seen:
            return
        await asyncio.sleep(0.1)


async def run(env: dict[str, str], audio: np.ndarray, ai: bool) -> dict[str, list[dict]]:
    seen: dict[str, list[dict]] = {}
    async with connect(f"ws://127.0.0.1:{ENGINE_PORT}", origin="tauri://localhost") as hud:  # as the app

        async def listen() -> None:
            async for raw in hud:
                message = json.loads(raw)
                seen.setdefault(message.get("type", "?"), []).append(message)
                if message.get("type") in ("segment", "fact_check"):
                    print(" ", message["type"], json.dumps(message.get("segment", message.get("alert")))[:160])

        listener = asyncio.create_task(listen())
        async with connect(f"ws://127.0.0.1:{TAB_PORT}", origin=ORIGIN) as tab:
            block = RATE // 10
            silence = np.zeros(RATE * 2, dtype=np.float32)
            for start in range(0, len(audio) + len(silence), block):
                chunk = np.concatenate([audio, silence])[start : start + block]
                await tab.send(chunk.astype("<f4").tobytes())
                await asyncio.sleep(0.1)  # real time, as a call would
        for _ in range(300):  # transcription and the fact check finish after the audio
            if "fact_check" in seen and "segment" in seen:
                break
            await asyncio.sleep(0.1)
        if ai:
            await wait_for(seen, "translation", 60)
            await hud.send(json.dumps({"type": "ask", "id": "q1", "question": "What budget did we mention for the website?"}))
            await wait_for(seen, "answer", 120)
        await hud.send(json.dumps({"type": "end_meeting"}))
        await wait_for(seen, "meeting_ended", 30)
        if ai:
            await wait_for(seen, "summary", 180)
        listener.cancel()
    return seen


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        env = {
            **os.environ,
            "CONTINUUM_SOURCES": "tab",
            "CONTINUUM_BROWSER_TAB_AUDIO": "1",
            "CONTINUUM_WS_PORT": str(ENGINE_PORT),
            "CONTINUUM_TENANT_ID": "check",
            "CONTINUUM_PROJECT_ID": "website",
            "CONTINUUM_MEMORY_DIR": str(folder / "memory"),
            "CONTINUUM_NOTES_DIR": str(folder / "notes"),
            "CONTINUUM_RECORD_AUDIO": "0",
        }
        ai = bool(env.get("CONTINUUM_LLM_PROVIDER"))
        if ai:
            env["CONTINUUM_TRANSLATE_TO"] = "tr"
        (folder / "plan.md").write_text(DOCUMENT, encoding="utf-8")
        subprocess.run(["continuum-import-docs", str(folder / "plan.md")], env=env, check=True)
        audio = spoken(SPEECH, folder)
        print(f"speech: {len(audio) / RATE:.1f}s")

        log = (folder / "engine.log").open("w")
        engine = subprocess.Popen(["continuum-engine"], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(600):  # loading the speech model can take a while the first time
                if engine.poll() is not None:
                    raise RuntimeError("engine exited:\n" + (folder / "engine.log").read_text()[-3000:])
                try:
                    with socket.create_connection(("127.0.0.1", TAB_PORT), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.2)
            seen = asyncio.run(run(env, audio, ai))
        finally:
            engine.terminate()
            try:
                engine.wait(10)
            except subprocess.TimeoutExpired:
                engine.kill()
                print("FAIL engine did not stop within 10 s of SIGTERM")
            log.close()
            print("--- engine log (end) ---\n" + (folder / "engine.log").read_text()[-2500:])

        text = " ".join(m["segment"]["text"] for m in seen.get("segment", []))
        alerts = [m["alert"] for m in seen.get("fact_check", [])]
        notes = list((folder / "notes").rglob("*.md"))
        checks = {
            "transcript mentions the budget": "budget" in text.lower(),
            "fact check: $50,000 said, $35,000 on record": any(
                "$50,000" in a["claimed"] and "$35,000" in a["recorded"] for a in alerts
            ),
            "meeting ended": "meeting_ended" in seen,
            "notes written": bool(notes) and "budget" in notes[0].read_text(encoding="utf-8").lower(),
        }
        if ai:
            summary = (seen.get("summary") or [{}])[0]
            answer = (seen.get("answer") or [{}])[0]
            print("  caption:", (seen.get("translation") or [{}])[0].get("text"))
            print("  answer:", answer.get("text") or answer.get("error"))
            print("  summary:", (summary.get("markdown") or summary.get("error") or "")[:300])
            checks |= {
                "Turkish caption": bool((seen.get("translation") or [{}])[0].get("text")),
                "answer cites the meeting": "50,000" in (answer.get("text") or "") or "50000" in (answer.get("text") or ""),
                "summary mentions the budget": "budget" in (summary.get("markdown") or "").lower(),
                "follow-up e-mail": bool((summary.get("email") or {}).get("body")),
            }
        for name, ok in checks.items():
            print(("PASS " if ok else "FAIL ") + name)
        if not all(checks.values()):
            print((folder / "engine.log").read_text()[-3000:])
        return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
