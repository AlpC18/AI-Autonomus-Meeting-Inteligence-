# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""FastMCP server for the Continuum action engine.

Registers the MCP tools an LLM can call. Phase 1 exposes only a health check;
tools that touch Jira, GitHub, Slack, or Calendar are added later behind an
approval gate.
"""

from importlib.metadata import version

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

mcp = FastMCP("continuum_actions")
"""The server instance. Import this to register tools or to test in-memory."""


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, idempotentHint=True, openWorldHint=False
    )
)
def continuum_health() -> dict[str, str]:
    """Report whether the Continuum action server is running.

    Read-only and side-effect free: it contacts no external service. Use it to
    confirm the server is reachable before calling other tools.

    Returns:
        ``{"status": "ok", "version": "<installed engine version>"}``.
    """
    return {"status": "ok", "version": version("continuum")}


def main() -> None:
    """Run the server over stdio (the ``continuum-actions`` console script).

    Blocks until the client disconnects.
    """
    mcp.run()
