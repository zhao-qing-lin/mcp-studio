# MCP Studio

Interactive debugger for [Model Context Protocol](https://modelcontextprotocol.io) servers — a Postman-style workflow for MCP tools.

Connect to a local MCP server over stdio, browse tools / resources / prompts, invoke tools with JSON arguments, inspect responses and latency, and replay recent calls from history.

## Features

- Stdio transport for local MCP servers
- Auto-discover tools, resources, and prompts
- Schema view + JSON argument editor
- Call tools and view responses with latency
- Local call history with one-click argument reload
- Terminal UI (Textual)

## Requirements

- Python 3.11+
- Windows / macOS / Linux

## Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\pip install -U pip
.venv\Scripts\pip install -e .
# macOS / Linux
.venv/bin/pip install -U pip
.venv/bin/pip install -e .
```

## Run

```bash
# Windows
.venv\Scripts\python -m mcp_studio
# macOS / Linux
.venv/bin/python -m mcp_studio
```

Or after install:

```bash
mcp-studio
```

The default command targets the bundled echo demo server. Press **Connect**, pick a tool, edit JSON args, then **Run**.

Keyboard shortcuts: `c` connect/disconnect · `r` run · `h` history · `q` quit

## Demo server

A small stdio MCP server is included for smoke testing (`echo`, `add`, `slow_echo`).

## Roadmap

- HTTP / SSE transports
- Load testing / latency profiles
- Mock MCP servers
- Schema validation & generated test cases
- Team collections and cloud sync

## License

MIT
