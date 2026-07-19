"""SQLite replay history for the local dashboard."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class HistoryEntry:
    id: int
    capsule_digest: str
    runner: str
    created_at: str
    technical_result: str
    behavioural_result: str | None
    error_summary: str | None


class SQLiteReplayHistory:
    """Append-only local summaries; source capsules are never stored or rewritten."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS replay_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capsule_digest TEXT NOT NULL,
                    runner TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    technical_result TEXT NOT NULL,
                    behavioural_result TEXT,
                    error_summary TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def append(
        self,
        *,
        capsule_digest: str,
        runner: str,
        technical_result: str,
        behavioural_result: str | None,
        error_summary: str | None,
    ) -> None:
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO replay_history (
                    capsule_digest, runner, created_at, technical_result,
                    behavioural_result, error_summary
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    capsule_digest,
                    runner,
                    created_at,
                    technical_result,
                    behavioural_result,
                    error_summary,
                ),
            )

    def recent(self, limit: int = 25) -> list[HistoryEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, capsule_digest, runner, created_at, technical_result,
                       behavioural_result, error_summary
                FROM replay_history ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [HistoryEntry(*row) for row in rows]
