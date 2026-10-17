# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Audio module: desktop loopback capture and Whisper transcription.

Produces timestamped transcript segments. It must not perform speaker
separation, memory writes, LLM calls, or action dispatch.
"""
