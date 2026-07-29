from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from mcp_studio.client import StudioMCPClient
from mcp_studio.history import list_recent, save
from mcp_studio.models import CallRecord, PromptInfo, ResourceInfo, ToolInfo

# app.py -> mcp_studio -> src -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_VENV_PY = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
_ECHO = PROJECT_ROOT / "examples" / "echo_server.py"
# Absolute paths for reliable Windows stdio spawn (display + execute)
DEFAULT_CMD = f'"{_VENV_PY}" "{_ECHO}"'
_CSS_FILE = Path(__file__).resolve().parent / "css" / "app.tcss"


def _load_css() -> str:
    """Load theme from css/app.tcss (resolved next to this module)."""
    try:
        return _CSS_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""


def _split_command(raw: str) -> list[str]:
    """Parse a command string into argv (Windows-friendly)."""
    raw = raw.strip()
    if not raw:
        return []
    try:
        return shlex.split(raw, posix=False)
    except ValueError:
        return raw.split()


def _pretty(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _sample_args(schema: dict[str, Any]) -> dict[str, Any]:
    """Build a starter JSON object from JSON Schema properties."""
    props = (schema or {}).get("properties") or {}
    sample: dict[str, Any] = {}
    for key, meta in props.items():
        meta = meta or {}
        t = meta.get("type")
        if t == "string":
            sample[key] = ""
        elif t == "integer":
            sample[key] = 0
        elif t == "number":
            sample[key] = 0.0
        elif t == "boolean":
            sample[key] = False
        elif t == "array":
            sample[key] = []
        elif t == "object":
            sample[key] = {}
        else:
            sample[key] = None
    return sample


def _format_response(record: CallRecord) -> str:
    body = record.result_text or ""
    if body.strip():
        try:
            body = _pretty(json.loads(body))
        except (json.JSONDecodeError, TypeError):
            pass
    if record.error:
        err = f"ERROR: {record.error}"
        body = f"{body}\n\n{err}" if body else err
    return body or "(empty)"


class HistoryScreen(ModalScreen[CallRecord | None]):
    """Recent calls — Enter/click reloads arguments into the main editor."""

    BINDINGS = [
        Binding("escape", "dismiss_none", "关闭", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._records: list[CallRecord] = []

    def compose(self) -> ComposeResult:
        self._records = list_recent(50)
        with Vertical(id="history-panel"):
            yield Label("调用历史 — Enter 回填参数 · Esc 关闭", id="history-title")
            items: list[ListItem] = []
            for r in self._records:
                mark = "✓" if r.ok else "✗"
                label = (
                    f"{mark} {r.tool_name:<24} {r.latency_ms:>7.1f} ms  {r.timestamp}"
                )
                items.append(ListItem(Label(label)))
            if not items:
                items.append(ListItem(Label("(暂无记录 — 运行 tool 后会出现在这里)")))
            yield ListView(*items, id="history-list")
            yield Button("关闭", id="history-close", variant="primary")

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#history-close")
    def _close(self) -> None:
        self.dismiss(None)

    @on(ListView.Selected, "#history-list")
    def _pick(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None or not (0 <= idx < len(self._records)):
            return
        self.dismiss(self._records[idx])


class MCPStudioApp(App[None]):
    """Postman-like MCP debugger TUI (stdio only)."""

    TITLE = "MCP Studio"
    SUB_TITLE = "local stdio debugger"
    # Prefer file under css/; loaded via __file__ so editable/src layout works
    CSS = _load_css()

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("c", "toggle_connect", "连接/断开"),
        Binding("r", "run_tool", "运行"),
        Binding("h", "show_history", "历史"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.client = StudioMCPClient()
        self.tools: list[ToolInfo] = []
        self.resources: list[ResourceInfo] = []
        self.prompts: list[PromptInfo] = []
        self._selected_tool: ToolInfo | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="top-bar"):
            yield Static("MCP Studio", id="brand")
            yield Input(
                value=DEFAULT_CMD,
                id="cmd-input",
                placeholder="stdio 命令：python.exe server.py",
            )
            yield Button("连接", id="btn-connect", variant="success")
            yield Button("断开", id="btn-disconnect", variant="error")
            yield Label("● 未连接", id="status")
        with Horizontal(id="main"):
            with Vertical(id="left"):
                with TabbedContent(id="catalog-tabs"):
                    with TabPane("Tools", id="tab-tools"):
                        yield ListView(id="tools-list")
                    with TabPane("Resources", id="tab-resources"):
                        yield ListView(id="resources-list")
                    with TabPane("Prompts", id="tab-prompts"):
                        yield ListView(id="prompts-list")
            with Vertical(id="center"):
                yield Label("Schema / Arguments", classes="panel-title")
                yield TextArea(
                    "选择左侧条目查看 schema",
                    id="schema",
                    read_only=True,
                )
                yield TextArea("{}", id="args")
                with Horizontal(id="run-row"):
                    yield Button("Run Tool", id="btn-run", variant="primary")
                    yield Label("", id="latency")
            with Vertical(id="right"):
                yield Label("Response", classes="panel-title")
                yield TextArea(
                    "连接 MCP Server → 选 tool → 编辑 JSON → Run（或按 r）",
                    id="response",
                    read_only=True,
                )
        yield Footer()

    def _status_widget(self) -> Label:
        return self.query_one("#status", Label)

    def _set_status(self, text: str, kind: str = "") -> None:
        w = self._status_widget()
        w.update(text)
        w.remove_class("connected", "error", "busy")
        if kind:
            w.add_class(kind)

    def _set_latency(self, text: str, kind: str = "") -> None:
        w = self.query_one("#latency", Label)
        w.update(text)
        w.remove_class("ok", "err")
        if kind:
            w.add_class(kind)

    # ---- connect / disconnect ----

    @on(Button.Pressed, "#btn-connect")
    def _on_connect_btn(self) -> None:
        self.connect_server()

    @on(Button.Pressed, "#btn-disconnect")
    def _on_disconnect_btn(self) -> None:
        self.disconnect_server()

    def action_toggle_connect(self) -> None:
        if self.client.connected:
            self.disconnect_server()
        else:
            self.connect_server()

    @work(exclusive=True, group="session")
    async def connect_server(self) -> None:
        raw = self.query_one("#cmd-input", Input).value
        cmd = _split_command(raw)
        if not cmd:
            self.notify("命令无效", severity="error")
            return
        self._set_status("● 连接中…", "busy")
        try:
            # Client API: connect_stdio(command: list[str], env=None, cwd=None)
            await self.client.connect_stdio(cmd, cwd=str(PROJECT_ROOT))
            self.tools = await self.client.list_tools()
            # Best-effort catalog extras (server may not support them)
            try:
                self.resources = await self.client.list_resources()
            except Exception:
                self.resources = []
            try:
                self.prompts = await self.client.list_prompts()
            except Exception:
                self.prompts = []
        except Exception as exc:
            self._set_status("● 连接失败", "error")
            self.notify(str(exc), severity="error")
            return

        await self._refresh_catalog_lists()
        n = len(self.tools)
        self._set_status(f"● 已连接 · {n} tools", "connected")
        self.notify(f"已连接 — {n} tools / {len(self.resources)} resources / {len(self.prompts)} prompts")

    @work(exclusive=True, group="session")
    async def disconnect_server(self) -> None:
        await self.client.disconnect()
        self.tools = []
        self.resources = []
        self.prompts = []
        self._selected_tool = None
        await self._refresh_catalog_lists()
        self.query_one("#schema", TextArea).text = "选择左侧条目查看 schema"
        self.query_one("#args", TextArea).text = "{}"
        self._set_status("● 未连接")
        self._set_latency("")
        self.notify("已断开")

    async def _refresh_catalog_lists(self) -> None:
        tools_lv = self.query_one("#tools-list", ListView)
        await tools_lv.clear()
        for t in self.tools:
            desc = (t.description or "").strip().replace("\n", " ")
            label = t.name if not desc else f"{t.name}  —  {desc[:48]}"
            await tools_lv.append(ListItem(Label(label), name=t.name))

        res_lv = self.query_one("#resources-list", ListView)
        await res_lv.clear()
        for r in self.resources:
            label = r.name or r.uri
            await res_lv.append(ListItem(Label(f"{label}\n  {r.uri}"), name=r.uri))
        if not self.resources:
            await res_lv.append(ListItem(Label("(无 resources)")))

        prompt_lv = self.query_one("#prompts-list", ListView)
        await prompt_lv.clear()
        for p in self.prompts:
            await prompt_lv.append(ListItem(Label(p.name), name=p.name))
        if not self.prompts:
            await prompt_lv.append(ListItem(Label("(无 prompts)")))

    # ---- selection ----

    @on(ListView.Selected, "#tools-list")
    def _on_tool_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None or not (0 <= idx < len(self.tools)):
            return
        self._show_tool(self.tools[idx])

    @on(ListView.Selected, "#resources-list")
    def _on_resource_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None or not (0 <= idx < len(self.resources)):
            return
        r = self.resources[idx]
        self._selected_tool = None
        self.query_one("#schema", TextArea).text = _pretty(
            {
                "uri": r.uri,
                "name": r.name,
                "description": r.description,
                "mimeType": r.mime_type,
            }
        )
        self.query_one("#args", TextArea).text = "{}"
        self.notify("Resources 为只读预览（MVP 不发起 read）", severity="information")

    @on(ListView.Selected, "#prompts-list")
    def _on_prompt_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None or not (0 <= idx < len(self.prompts)):
            return
        p = self.prompts[idx]
        self._selected_tool = None
        self.query_one("#schema", TextArea).text = _pretty(
            {
                "name": p.name,
                "description": p.description,
                "arguments": p.arguments,
            }
        )
        self.query_one("#args", TextArea).text = "{}"
        self.notify("Prompts 为只读预览（MVP 不发起 get）", severity="information")

    def _show_tool(self, tool: ToolInfo) -> None:
        self._selected_tool = tool
        self.query_one("#schema", TextArea).text = _pretty(
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
        )
        sample = _sample_args(tool.input_schema or {})
        self.query_one("#args", TextArea).text = _pretty(sample if sample else {})

    def _select_tool_by_name(self, name: str) -> None:
        for i, t in enumerate(self.tools):
            if t.name == name:
                self._show_tool(t)
                try:
                    self.query_one("#tools-list", ListView).index = i
                except Exception:
                    pass
                return

    # ---- run ----

    @on(Button.Pressed, "#btn-run")
    def _on_run_btn(self) -> None:
        self.action_run_tool()

    def action_run_tool(self) -> None:
        self.run_selected_tool()

    @work(exclusive=True, group="call")
    async def run_selected_tool(self) -> None:
        if not getattr(self.client, "connected", False):
            self.notify("请先连接（c 或点「连接」）", severity="warning")
            return
        if not self._selected_tool:
            self.notify("请先在 Tools 里选择一个 tool", severity="warning")
            return

        raw = self.query_one("#args", TextArea).text
        try:
            args = json.loads(raw) if raw.strip() else {}
            if not isinstance(args, dict):
                raise ValueError("参数必须是 JSON 对象 {}")
        except Exception as exc:
            self.notify(f"JSON 无效: {exc}", severity="error")
            return

        self._set_latency("运行中…", "")
        # Client API: call_tool(name, arguments) -> CallRecord (includes latency_ms)
        record = await self.client.call_tool(self._selected_tool.name, args)
        try:
            save(record)
        except Exception as exc:
            self.notify(f"历史保存失败: {exc}", severity="warning")

        kind = "ok" if record.ok else "err"
        self._set_latency(
            f"{'OK' if record.ok else 'ERR'} · {record.latency_ms:.1f} ms",
            kind,
        )
        self.query_one("#response", TextArea).text = _format_response(record)

    # ---- history ----

    def action_show_history(self) -> None:
        def _apply(record: CallRecord | None) -> None:
            if record is None:
                return
            self._select_tool_by_name(record.tool_name)
            self.query_one("#args", TextArea).text = _pretty(record.arguments or {})
            self.query_one("#response", TextArea).text = _format_response(record)
            kind = "ok" if record.ok else "err"
            self._set_latency(
                f"历史 · {'OK' if record.ok else 'ERR'} · {record.latency_ms:.1f} ms",
                kind,
            )
            self.notify(f"已回填 {record.tool_name}")

        self.push_screen(HistoryScreen(), _apply)


def run() -> None:
    """Start the MCP Studio Textual app."""
    MCPStudioApp().run()
