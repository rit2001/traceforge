#!/usr/bin/env python3
"""Create one controlled, offline Workbench catalog for manual UI review."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from traceforge import CaptureSession, seal_capsule, validate_capsule
from traceforge.assembly import SQLiteAssemblyState
from traceforge.history import SQLiteReplayHistory
from traceforge.kafka_runtime import capsule_events

CAPTURE_ID = "controlled-agentic-review"
CAPSULE_ID = "controlled-agentic-review-v1"
DEFAULT_OUTPUT = Path.home() / ".traceforge" / "workbench-review"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_MARKER = ".traceforge-workbench-review"
_MARKER_CONTENT = "traceforge-workbench-review-v1\n"
_OWNED_NAMES = {
    _MARKER,
    "assembly.sqlite3",
    "assembly.sqlite3-shm",
    "assembly.sqlite3-wal",
    "history.sqlite3",
    "history.sqlite3-shm",
    "history.sqlite3-wal",
    "capsules",
}


@dataclass(frozen=True)
class ReviewDataPaths:
    root: Path
    assembly_database: Path
    capsule_directory: Path
    history_database: Path


def _is_inside_repository(path: Path) -> bool:
    try:
        path.relative_to(REPOSITORY_ROOT)
    except ValueError:
        return False
    return True


def _validate_owned_target(output: Path) -> None:
    if _is_inside_repository(output):
        raise ValueError("review data output must be outside the repository")
    if output.is_symlink():
        raise ValueError("review data output cannot be a symlink")
    if not output.exists():
        return
    if not output.is_dir():
        raise ValueError("review data output must be a directory")
    entries = {item.name for item in output.iterdir()}
    if not entries:
        return
    marker = output / _MARKER
    if not marker.is_file() or marker.is_symlink():
        raise ValueError("refusing to replace a directory not owned by the review-data generator")
    if marker.read_text(encoding="utf-8") != _MARKER_CONTENT:
        raise ValueError("review data ownership marker is invalid")
    unexpected = entries - _OWNED_NAMES
    if unexpected:
        raise ValueError("review data directory contains files not owned by the generator")
    capsules = output / "capsules"
    if capsules.exists():
        if capsules.is_symlink() or not capsules.is_dir():
            raise ValueError("review capsule directory is not a safe local directory")
        capsule_entries = list(capsules.iterdir())
        expected = capsules / f"{CAPTURE_ID}.json"
        if any(
            item != expected or item.is_symlink() or not item.is_file() for item in capsule_entries
        ):
            raise ValueError("review capsule directory contains unexpected files")


def _remove_owned_target(output: Path) -> None:
    if not output.exists():
        return
    _validate_owned_target(output)
    capsules = output / "capsules"
    if capsules.exists():
        capsule = capsules / f"{CAPTURE_ID}.json"
        if capsule.exists():
            capsule.unlink()
        capsules.rmdir()
    for name in sorted(_OWNED_NAMES - {"capsules"}):
        path = output / name
        if path.exists():
            path.unlink()
    output.rmdir()


def _controlled_capsule() -> dict[str, Any]:
    session = CaptureSession(
        schema_version="0.2.0",
        capsule_id=CAPSULE_ID,
        run_id=CAPTURE_ID,
        capture_kind="controlled_fixture",
        producer={"name": "traceforge-review-data", "version": "1"},
        subject={
            "application": "Agentic Chatbot — Controlled Demo",
            "revision": "synthetic-review-v1",
            "framework": "tool-calling",
            "language": "Python",
        },
        operation="answer_with_web_search",
        invocation_input={"question": "What does the controlled TraceForge review demonstrate?"},
        recorded_at="2026-10-04T00:00:00Z",
    )
    session.record_model(
        "chat.completions",
        {
            "model": "controlled-review-model",
            "payload": {
                "messages": [
                    {
                        "role": "user",
                        "content": "What does the controlled TraceForge review demonstrate?",
                    }
                ]
            },
        },
        lambda request: {
            "payload": {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_call": {
                        "name": "web.search",
                        "arguments": {"query": "TraceForge replay evidence"},
                    },
                }
            }
        },
    )
    session.record_tool(
        "web.search",
        {"query": "TraceForge replay evidence"},
        lambda arguments: {
            "results": [
                {
                    "title": "Controlled TraceForge evidence",
                    "summary": "Synthetic reviewed evidence supports deterministic offline replay.",
                }
            ],
            "query": arguments["query"],
        },
    )
    session.record_model(
        "chat.completions",
        {
            "model": "controlled-review-model",
            "payload": {
                "messages": [
                    {"role": "user", "content": "Summarize the recorded search result."},
                    {
                        "role": "tool",
                        "name": "web.search",
                        "content": (
                            "Synthetic reviewed evidence supports deterministic offline replay."
                        ),
                    },
                ]
            },
        },
        lambda request: {
            "payload": {
                "message": {
                    "role": "assistant",
                    "content": "The controlled run demonstrates deterministic offline replay.",
                }
            }
        },
    )
    session.record_event("execution", "completed", {"dependency_count": 3})
    draft = session.finish(
        "completed",
        {"answer": "The controlled run demonstrates deterministic offline replay."},
    )
    capsule = seal_capsule(draft)
    validate_capsule(capsule)
    return capsule


def create_review_data(output: Path = DEFAULT_OUTPUT) -> ReviewDataPaths:
    """Safely replace one generator-owned directory with controlled review data."""
    requested = output.expanduser()
    if requested.is_symlink():
        raise ValueError("review data output cannot be a symlink")
    target = requested.resolve()
    _validate_owned_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".workbench-review-build-", dir=target.parent))
    try:
        (staging / _MARKER).write_text(_MARKER_CONTENT, encoding="utf-8")
        capsule = _controlled_capsule()
        assembly_database = staging / "assembly.sqlite3"
        capsule_directory = staging / "capsules"
        state = SQLiteAssemblyState(assembly_database, capsule_directory)
        try:
            for event in capsule_events(capsule, CAPTURE_ID):
                state.process(event)
        finally:
            state.close()
        SQLiteReplayHistory(staging / "history.sqlite3")
        _remove_owned_target(target)
        staging.rename(target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return ReviewDataPaths(
        root=target,
        assembly_database=target / "assembly.sqlite3",
        capsule_directory=target / "capsules",
        history_database=target / "history.sqlite3",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    paths = create_review_data(args.output)
    print(
        json.dumps(
            {
                "assembly_database": str(paths.assembly_database),
                "capsule_directory": str(paths.capsule_directory),
                "history_database": str(paths.history_database),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
