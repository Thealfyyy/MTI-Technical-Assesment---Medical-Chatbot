"""Small SQLite persistence layer for demo handoffs and operational analytics."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings


class SQLiteStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_settings().sqlite_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS handoffs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    contact_name TEXT NOT NULL,
                    contact_method TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    language TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    retrieval_ms REAL NOT NULL,
                    generation_ms REAL NOT NULL,
                    total_ms REAL NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_handoff(self, session_id: str, summary: str, contact_name: str, contact_method: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO handoffs(session_id,summary,contact_name,contact_method,created_at) VALUES(?,?,?,?,?)",
                (session_id, summary, contact_name, contact_method, datetime.now(timezone.utc).isoformat()),
            )
            return int(cursor.lastrowid)

    def record_conversation(
        self,
        *,
        session_id: str,
        question: str,
        status: str,
        language: str,
        model: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        retrieval_ms: float,
        generation_ms: float,
        total_ms: float,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO conversations(
                    session_id,question,status,language,model,prompt_tokens,completion_tokens,
                    retrieval_ms,generation_ms,total_ms,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (session_id, question, status, language, model, prompt_tokens, completion_tokens,
                 retrieval_ms, generation_ms, total_ms, datetime.now(timezone.utc).isoformat()),
            )

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = max(0, min(len(ordered) - 1, int(round((percentile / 100) * (len(ordered) - 1)))))
        return round(ordered[index], 2)

    def analytics(self, limit: int = 10) -> dict[str, Any]:
        with self._connect() as connection:
            volume = connection.execute("SELECT COUNT(*) AS n FROM conversations").fetchone()["n"]
            top_questions = [dict(row) for row in connection.execute(
                "SELECT question, COUNT(*) AS count FROM conversations GROUP BY question ORDER BY count DESC, question LIMIT ?",
                (limit,),
            )]
            unanswered = connection.execute(
                "SELECT COUNT(*) AS n FROM conversations WHERE status IN ('out_of_scope','escalated')"
            ).fetchone()["n"]
            totals = connection.execute(
                "SELECT COALESCE(SUM(prompt_tokens),0) AS prompt, COALESCE(SUM(completion_tokens),0) AS completion FROM conversations"
            ).fetchone()
            rows = connection.execute("SELECT total_ms,retrieval_ms,generation_ms FROM conversations").fetchall()
        total_ms = [float(r["total_ms"]) for r in rows]
        retrieval_ms = [float(r["retrieval_ms"]) for r in rows]
        generation_ms = [float(r["generation_ms"]) for r in rows]
        return {
            "conversation_volume": int(volume),
            "top_questions": top_questions,
            "unanswered_count": int(unanswered),
            "tokens": {"prompt": int(totals["prompt"]), "completion": int(totals["completion"])},
            "latency_ms": {
                "total_p50": self._percentile(total_ms, 50), "total_p95": self._percentile(total_ms, 95),
                "total_max": max(total_ms) if total_ms else None,
                "retrieval_p50": self._percentile(retrieval_ms, 50),
                "generation_p50": self._percentile(generation_ms, 50),
            },
            "record_count": len(rows),
        }

    def conversation_metrics(self, session_id: str) -> dict[str, Any] | None:
        """Return telemetry for a session without exposing its stored question text."""
        with self._connect() as connection:
            row = connection.execute(
                """SELECT session_id,status,language,model,prompt_tokens,completion_tokens,
                          retrieval_ms,generation_ms,total_ms,created_at
                   FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT 1""",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

