from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from mcp_studio.models import CallRecord

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = _PROJECT_ROOT / "tmp" / "history.db"


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calls (
            id TEXT PRIMARY KEY,
            tool_name TEXT NOT NULL,
            arguments TEXT NOT NULL,
            result_text TEXT NOT NULL,
            ok INTEGER NOT NULL,
            latency_ms REAL NOT NULL,
            timestamp TEXT NOT NULL,
            error TEXT
        )
        """
    )
    conn.commit()
    return conn


def save(record: CallRecord) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO calls
            (id, tool_name, arguments, result_text, ok, latency_ms, timestamp, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.tool_name,
                json.dumps(record.arguments, ensure_ascii=False),
                record.result_text,
                1 if record.ok else 0,
                record.latency_ms,
                record.timestamp,
                record.error,
            ),
        )
        conn.commit()


def list_recent(limit: int = 50) -> list[CallRecord]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, tool_name, arguments, result_text, ok, latency_ms, timestamp, error
            FROM calls
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        CallRecord(
            id=r[0],
            tool_name=r[1],
            arguments=json.loads(r[2] or "{}"),
            result_text=r[3] or "",
            ok=bool(r[4]),
            latency_ms=float(r[5] or 0),
            timestamp=r[6],
            error=r[7],
        )
        for r in rows
    ]


def clear() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM calls")
        conn.commit()
