# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Fact-check module: flags live statements that contradict the record.

Compares what is being said with what memory holds for the same tenant and
project. It must not capture audio, store anything, or talk to the desktop
app; it only turns a segment plus memory hits into an alert or nothing.
"""
