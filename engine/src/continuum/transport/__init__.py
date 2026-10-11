# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Transport module: streams engine output to the desktop app.

Owns the local WebSocket that carries live transcript segments to the HUD.
It must not capture, transcribe, or store anything itself.
"""
