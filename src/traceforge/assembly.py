"""SQLite-backed idempotent capture-event assembly."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from traceforge.canonical import canonicalize
from traceforge.capture_events import sanitize_and_validate_event
from traceforge.exceptions import SemanticValidationError
from traceforge.sealing import seal_capsule
from traceforge.store import JsonFileCapsuleStore


class AssemblyError(SemanticValidationError):
    """A capture stream cannot be assembled safely."""


class SequenceGapError(AssemblyError):
    """An event did not follow the durable per-capture sequence."""


class ConflictingDuplicateError(AssemblyError):
    """An event_id was reused for different content."""


@dataclass(frozen=True)
class ProcessResult:
    duplicate: bool
    completed: bool
    capsule_path: Path | None = None


class AssemblyState(Protocol):
    def process(self, event: dict[str, Any]) -> ProcessResult: ...
    def capture(self, capture_id: str) -> dict[str, Any] | None: ...
    def close(self) -> None: ...


class SQLiteAssemblyState:
    """Durable ordered assembly and idempotency state for a local worker."""

    def __init__(self, database: Path, capsule_directory: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        capsule_directory.mkdir(parents=True, exist_ok=True)
        self._capsule_directory = capsule_directory.resolve()
        self._connection = sqlite3.connect(database)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "event_id TEXT PRIMARY KEY, capture_id TEXT NOT NULL, "
            "sequence INTEGER NOT NULL, body BLOB NOT NULL, UNIQUE(capture_id, sequence))"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS captures ("
            "capture_id TEXT PRIMARY KEY, last_sequence INTEGER NOT NULL, "
            "completed INTEGER NOT NULL DEFAULT 0, capsule_path TEXT)"
        )
        self._connection.commit()

    def process(self, event: dict[str, Any]) -> ProcessResult:
        safe = sanitize_and_validate_event(event)
        body = canonicalize(safe)
        existing = self._connection.execute(
            "SELECT body FROM events WHERE event_id = ?", (safe["event_id"],)
        ).fetchone()
        if existing is not None:
            if existing[0] != body:
                raise ConflictingDuplicateError(
                    f"event_id {safe['event_id']!r} has conflicting content"
                )
            row = self._connection.execute(
                "SELECT completed, capsule_path FROM captures WHERE capture_id = ?",
                (safe["capture_id"],),
            ).fetchone()
            return ProcessResult(
                True, bool(row and row[0]), Path(row[1]) if row and row[1] else None
            )

        row = self._connection.execute(
            "SELECT last_sequence, completed FROM captures WHERE capture_id = ?",
            (safe["capture_id"],),
        ).fetchone()
        expected = 1 if row is None else row[0] + 1
        if safe["sequence"] != expected:
            raise SequenceGapError(
                f"capture {safe['capture_id']!r} expected sequence {expected}, "
                f"got {safe['sequence']}"
            )
        if row and row[1]:
            raise AssemblyError(f"capture {safe['capture_id']!r} is already sealed")

        with self._connection:
            self._connection.execute(
                "INSERT INTO events(event_id, capture_id, sequence, body) VALUES (?, ?, ?, ?)",
                (safe["event_id"], safe["capture_id"], safe["sequence"], body),
            )
            self._connection.execute(
                "INSERT INTO captures(capture_id, last_sequence, completed) VALUES (?, ?, 0) "
                "ON CONFLICT(capture_id) DO UPDATE SET last_sequence=excluded.last_sequence",
                (safe["capture_id"], safe["sequence"]),
            )
            if safe["event_type"] != "capture_completed":
                return ProcessResult(False, False)

            draft = self._assemble(safe["capture_id"])
            sealed = seal_capsule(draft)
            target = self._capsule_directory / f"{safe['capture_id']}.json"
            JsonFileCapsuleStore().save(target, sealed)
            self._connection.execute(
                "UPDATE captures SET completed=1, capsule_path=? WHERE capture_id=?",
                (str(target), safe["capture_id"]),
            )
            return ProcessResult(False, True, target)

    def _assemble(self, capture_id: str) -> dict[str, Any]:
        rows = self._connection.execute(
            "SELECT body FROM events WHERE capture_id=? ORDER BY sequence", (capture_id,)
        ).fetchall()
        events = [json.loads(row[0]) for row in rows]
        if not events or events[0]["event_type"] != "capture_started":
            raise AssemblyError("capture stream must start with capture_started")
        draft = dict(events[0]["payload"])
        draft["dependencies"] = [
            item["payload"] for item in events if item["event_type"] == "dependency_recorded"
        ]
        observations = [
            item["payload"] for item in events if item["event_type"] == "observation_recorded"
        ]
        completed = events[-1]
        if completed["event_type"] != "capture_completed":
            raise AssemblyError("capture_completed must terminate the stream")
        draft["original_observation"] = completed["payload"]["original_observation"]
        if observations:
            draft["original_observation"]["events"] = observations
        draft["redaction"] = completed["payload"]["redaction"]
        return draft

    def capture(self, capture_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT last_sequence, completed, capsule_path FROM captures WHERE capture_id=?",
            (capture_id,),
        ).fetchone()
        return (
            None
            if row is None
            else {"last_sequence": row[0], "completed": bool(row[1]), "capsule_path": row[2]}
        )

    def close(self) -> None:
        self._connection.close()
