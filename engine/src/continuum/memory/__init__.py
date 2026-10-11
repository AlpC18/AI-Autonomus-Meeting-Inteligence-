# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Memory module: vector and SQLite storage for retrieval (RAG).

Every read and write must be scoped by tenant_id and project_id so one
client's data can never be returned for another. It must not capture audio or
dispatch actions.
Intentionally empty until the memory phase.
"""
