# Bug Fixes

Log every bug fix, crash resolution, audio loopback fix, or API rate-limit patch here (`AI_GUIDELINES.md` §3). Newest first.

| Date | Module | Problem | Fix |
| :--- | :--- | :--- | :--- |
| 2026-10-12 | diarization | Words that Whisper returns with no duration kept the "others" label inside a labelled segment. | They take the speaker of the turn their start time falls in. |
