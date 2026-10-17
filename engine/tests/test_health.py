# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Checks the actions MCP server answers through the real MCP protocol."""

from fastmcp import Client

from recall.actions.server import mcp


async def test_health_reports_ok_and_version() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("recall_health")

    assert result.data["status"] == "ok"
    assert result.data["version"]
