"""Minimal stdio MCP server for MCP Studio demos."""

from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("echo-server")


@mcp.tool()
def echo(text: str) -> str:
    """Echo back the given text."""
    return text


@mcp.tool()
def add(a: float, b: float) -> float:
    """Return a + b."""
    return a + b


@mcp.tool()
async def slow_echo(text: str, delay_ms: int = 500) -> str:
    """Sleep for delay_ms then echo text (latency demo)."""
    await asyncio.sleep(max(delay_ms, 0) / 1000.0)
    return text


if __name__ == "__main__":
    mcp.run(transport="stdio")
