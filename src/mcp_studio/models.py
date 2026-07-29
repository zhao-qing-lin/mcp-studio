from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolInfo:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceInfo:
    uri: str
    name: str = ""
    description: str = ""
    mime_type: str | None = None


@dataclass
class PromptInfo:
    name: str
    description: str = ""
    arguments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ServerCaps:
    tools: bool = False
    resources: bool = False
    prompts: bool = False


@dataclass
class CallRecord:
    id: str
    tool_name: str
    arguments: dict[str, Any]
    result_text: str
    ok: bool
    latency_ms: float
    timestamp: str
    error: str | None = None
