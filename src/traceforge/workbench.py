"""Read-only original-run catalog for the local Workbench."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from traceforge.canonical import canonicalize
from traceforge.dependencies import assert_replayable_tool_failures
from traceforge.exceptions import TraceForgeError
from traceforge.store import JsonFileCapsuleStore
from traceforge.validation import validate_capsule

_CAPTURE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


@dataclass(frozen=True)
class RunSummary:
    """Detached presentation-neutral summary of one operational capture."""

    run_id: str
    completed: bool
    replayable: bool
    evidence_state: str
    capsule_id: str | None
    schema_version: str | None
    subject: str | None
    recorded_at: str | None
    trace_id: str | None
    span_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "completed": self.completed,
            "replayable": self.replayable,
            "evidence_state": self.evidence_state,
            "capsule_id": self.capsule_id,
            "schema_version": self.schema_version,
            "subject": self.subject,
            "recorded_at": self.recorded_at,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
        }


@dataclass(frozen=True)
class RunDetail:
    """Alias-isolated run detail with validated capsule presentation data."""

    summary: RunSummary
    last_sequence: int
    evidence_reason: str | None
    evidence_available: bool
    _canonical_capsule: bytes | None = None

    def to_dict(self) -> dict[str, Any]:
        result = self.summary.to_dict()
        capsule = None if self._canonical_capsule is None else json.loads(self._canonical_capsule)
        evidence = {
            "state": self.summary.evidence_state,
            "reason": self.evidence_reason,
            "available": self.evidence_available,
            "sealed": capsule is not None,
            "integrity_verified": capsule is not None,
            "capsule_id": self.summary.capsule_id,
            "schema_version": self.summary.schema_version,
            "digest": None if capsule is None else capsule["integrity"]["digest"],
        }
        result.update(
            {
                "last_sequence": self.last_sequence,
                "evidence": evidence,
                "subject_details": None if capsule is None else capsule["subject"],
                "producer": None if capsule is None else capsule["producer"],
                "capture_metadata": None if capsule is None else capsule["capture"],
                "invocation": None if capsule is None else capsule["invocation"],
                "dependencies": [] if capsule is None else capsule["dependencies"],
                "original_execution": (
                    None
                    if capsule is None
                    else {
                        "status": capsule["original_observation"]["execution_status"],
                        "events": capsule["original_observation"]["events"],
                        "output": capsule["original_observation"]["output"],
                        "error": capsule["original_observation"]["error"],
                    }
                ),
            }
        )
        return result


@dataclass(frozen=True)
class RunCatalogSnapshot:
    """Path-free source state plus detached original-run summaries."""

    source_state: str
    source_reason: str | None
    runs: tuple[RunSummary, ...]

    def source_dict(self) -> dict[str, Any]:
        return {
            "state": self.source_state,
            "reason": self.source_reason,
            "run_count": len(self.runs),
        }


@dataclass(frozen=True)
class _CaptureRecord:
    run_id: str
    last_sequence: int
    completed: bool
    capsule_path: str | None
    trace_id: str | None
    span_id: str | None


@dataclass(frozen=True)
class _CatalogRead:
    source_state: str
    source_reason: str | None
    records: tuple[_CaptureRecord, ...]


class SQLiteRunCatalog:
    """Read assembly metadata and referenced sealed evidence without writing either."""

    def __init__(self, database: Path | None, capsule_directory: Path | None = None) -> None:
        self._database = None if database is None else database.resolve()
        self._capsule_directory = None if capsule_directory is None else capsule_directory.resolve()
        self._store = JsonFileCapsuleStore()

    def list(self) -> list[RunSummary]:
        return list(self.snapshot().runs)

    def snapshot(self) -> RunCatalogSnapshot:
        """Return source health and current runs without exposing configured paths."""
        result = self._read()
        return RunCatalogSnapshot(
            source_state=result.source_state,
            source_reason=result.source_reason,
            runs=tuple(self._resolve(record).summary for record in result.records),
        )

    def get(self, run_id: str) -> RunDetail | None:
        record = next((item for item in self._read().records if item.run_id == run_id), None)
        return None if record is None else self._resolve(record)

    def _connect(self) -> sqlite3.Connection:
        if self._database is None:  # pragma: no cover - guarded by _read
            raise sqlite3.OperationalError("assembly database is not configured")
        return sqlite3.connect(f"{self._database.as_uri()}?mode=ro", uri=True)

    def _read(self) -> _CatalogRead:
        if self._database is None:
            return _CatalogRead("not-configured", "not-configured", ())
        if not self._database.is_file():
            return _CatalogRead("unavailable", "database-missing", ())
        try:
            connection = self._connect()
        except sqlite3.Error:
            return _CatalogRead("unavailable", "database-unopenable", ())
        try:
            if not self._has_capture_table(connection):
                return _CatalogRead("unavailable", "capture-table-missing", ())
            rows = connection.execute(
                "SELECT capture_id, last_sequence, completed, capsule_path, trace_id, span_id "
                "FROM captures ORDER BY capture_id"
            ).fetchall()
            return _CatalogRead("ready", None, tuple(self._from_row(row) for row in rows))
        except sqlite3.Error:
            return _CatalogRead("unavailable", "database-unreadable", ())
        finally:
            connection.close()

    @staticmethod
    def _has_capture_table(connection: sqlite3.Connection) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='captures'"
        ).fetchone()
        return row is not None

    @staticmethod
    def _from_row(row: tuple[Any, ...]) -> _CaptureRecord:
        return _CaptureRecord(
            run_id=row[0],
            last_sequence=row[1],
            completed=bool(row[2]),
            capsule_path=row[3],
            trace_id=row[4],
            span_id=row[5],
        )

    def _capsule_path(self, record: _CaptureRecord) -> Path | None:
        recorded = Path(record.capsule_path) if record.capsule_path else None
        if recorded is not None and recorded.is_file():
            return recorded
        if self._capsule_directory is None or not _CAPTURE_ID.fullmatch(record.run_id):
            return None
        candidate = (self._capsule_directory / f"{record.run_id}.json").resolve()
        try:
            candidate.relative_to(self._capsule_directory)
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    def _resolve(self, record: _CaptureRecord) -> RunDetail:
        state = "pending"
        reason: str | None = "capture-incomplete"
        available = False
        capsule: dict[str, Any] | None = None
        canonical_capsule: bytes | None = None
        replayable = False

        if record.completed and not record.capsule_path:
            state = "missing"
            reason = "capsule-reference-missing"
        elif record.completed:
            try:
                capsule_path = self._capsule_path(record)
                if capsule_path is None:
                    state = "missing"
                    reason = "capsule-file-missing"
                else:
                    available = True
                    loaded = self._store.load(capsule_path)
                    validate_capsule(loaded)
                    capsule = loaded
                    canonical_capsule = canonicalize(capsule)
                    state = "verified"
                    reason = None
                    try:
                        assert_replayable_tool_failures(capsule["dependencies"])
                        replayable = True
                    except TraceForgeError:
                        reason = "unsupported-recorded-error"
            except (
                TraceForgeError,
                KeyError,
                OSError,
                RecursionError,
                TypeError,
                UnicodeError,
                ValueError,
            ):
                capsule = None
                canonical_capsule = None
                replayable = False
                state = "invalid"
                reason = "validation-failed"

        summary = RunSummary(
            run_id=record.run_id,
            completed=record.completed,
            replayable=replayable,
            evidence_state=state,
            capsule_id=None if capsule is None else capsule["capsule_id"],
            schema_version=None if capsule is None else capsule["schema_version"],
            subject=(None if capsule is None else capsule["subject"].get("application")),
            recorded_at=(None if capsule is None else capsule["capture"].get("recorded_at")),
            trace_id=record.trace_id,
            span_id=record.span_id,
        )
        return RunDetail(
            summary=summary,
            last_sequence=record.last_sequence,
            evidence_reason=reason,
            evidence_available=available,
            _canonical_capsule=canonical_capsule,
        )
