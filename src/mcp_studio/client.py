from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from mcp_studio.models import (
    CallRecord,
    PromptInfo,
    ResourceInfo,
    ServerCaps,
    ToolInfo,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_to_text(content: list[Any]) -> str:
    parts: list[str] = []
    for item in content:
        if isinstance(item, TextContent):
            parts.append(item.text)
        elif hasattr(item, "text"):
            parts.append(str(item.text))
        else:
            try:
                parts.append(item.model_dump_json())
            except Exception:
                parts.append(str(item))
    return "\n".join(parts) if parts else ""


class StudioMCPClient:
    """Async stdio MCP client with a single owner task for the session lifetime."""

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._error: BaseException | None = None
        self.caps = ServerCaps()
        self.connected = False
        self.command: list[str] = []

    async def _session_owner(self, params: StdioServerParameters) -> None:
        try:
            async with stdio_client(params) as streams:
                read, write = streams
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    caps = getattr(init, "capabilities", None)
                    self.caps = ServerCaps(
                        tools=bool(caps and getattr(caps, "tools", None)),
                        resources=bool(caps and getattr(caps, "resources", None)),
                        prompts=bool(caps and getattr(caps, "prompts", None)),
                    )
                    self._session = session
                    self.connected = True
                    self._ready.set()
                    await self._stop.wait()
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            self._error = exc
            self._ready.set()
        finally:
            self._session = None
            self.connected = False
            self.caps = ServerCaps()

    async def connect_stdio(
        self,
        command: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        if not command:
            raise RuntimeError("命令不能为空")
        await self.disconnect()

        params = StdioServerParameters(
            command=command[0],
            args=list(command[1:]),
            env=env,
            cwd=cwd,
        )
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._error = None
        self.command = list(command)
        self._task = asyncio.create_task(self._session_owner(params))
        await self._ready.wait()
        if self._error is not None or self._session is None:
            err = self._error or RuntimeError("未知连接错误")
            await self.disconnect()
            raise RuntimeError(f"连接 MCP Server 失败: {err}") from self._error

    async def disconnect(self) -> None:
        self._stop.set()
        task = self._task
        self._task = None
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=5)
            except (asyncio.TimeoutError, Exception):
                task.cancel()
                try:
                    await task
                except Exception:
                    pass
        self._session = None
        self.connected = False
        self.caps = ServerCaps()

    def _require_session(self) -> ClientSession:
        if not self._session or not self.connected:
            raise RuntimeError("尚未连接 MCP Server")
        return self._session

    async def list_tools(self) -> list[ToolInfo]:
        session = self._require_session()
        result = await session.list_tools()
        return [
            ToolInfo(
                name=t.name,
                description=t.description or "",
                input_schema=dict(t.inputSchema or {}),
            )
            for t in result.tools
        ]

    async def list_resources(self) -> list[ResourceInfo]:
        session = self._require_session()
        try:
            result = await session.list_resources()
        except Exception:
            return []
        return [
            ResourceInfo(
                uri=str(r.uri),
                name=r.name or "",
                description=r.description or "",
                mime_type=getattr(r, "mimeType", None),
            )
            for r in result.resources
        ]

    async def list_prompts(self) -> list[PromptInfo]:
        session = self._require_session()
        try:
            result = await session.list_prompts()
        except Exception:
            return []
        return [
            PromptInfo(
                name=p.name,
                description=p.description or "",
                arguments=[
                    a.model_dump() if hasattr(a, "model_dump") else dict(a)
                    for a in (p.arguments or [])
                ],
            )
            for p in result.prompts
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallRecord:
        started = time.perf_counter()
        record_id = uuid.uuid4().hex[:12]
        ts = _utc_now()
        try:
            session = self._require_session()
            result = await session.call_tool(name, arguments)
            latency = (time.perf_counter() - started) * 1000
            text = _content_to_text(list(result.content or []))
            is_error = bool(getattr(result, "isError", False))
            structured = getattr(result, "structuredContent", None)
            if not text and structured is not None:
                text = json.dumps(structured, ensure_ascii=False, indent=2)
            return CallRecord(
                id=record_id,
                tool_name=name,
                arguments=arguments,
                result_text=text,
                ok=not is_error,
                latency_ms=latency,
                timestamp=ts,
                error="tool returned isError" if is_error else None,
            )
        except Exception as exc:
            latency = (time.perf_counter() - started) * 1000
            return CallRecord(
                id=record_id,
                tool_name=name,
                arguments=arguments,
                result_text="",
                ok=False,
                latency_ms=latency,
                timestamp=ts,
                error=str(exc),
            )
