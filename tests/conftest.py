"""Shared synthetic Replay Capsule builders."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def capsule_draft() -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "capsule_id": "capsule-test-1",
        "capture": {
            "run_id": "run-test-1",
            "kind": "controlled_fixture",
            "recorded_at": "2026-07-19T12:00:00Z",
        },
        "producer": {"name": "traceforge-tests", "version": "0.1.0"},
        "subject": {
            "application": "synthetic-application",
            "revision": "revision-1",
            "framework": "LangGraph",
            "language": "Python",
        },
        "invocation": {
            "operation": "synthetic-operation",
            "input": {"nested": [1, True, None]},
        },
        "dependencies": [
            {
                "dependency_id": "dependency-1",
                "sequence": 1,
                "kind": "model",
                "operation": "generate",
                "request": {
                    "model": "synthetic-model",
                    "payload": {"messages": [{"role": "user", "content": "synthetic"}]},
                },
                "outcome": {
                    "status": "returned",
                    "response": {"payload": {"content": "synthetic-response"}},
                },
                "duration_ms": 0,
            }
        ],
        "original_observation": {
            "execution_status": "completed",
            "events": [
                {
                    "event_id": "event-1",
                    "sequence": 1,
                    "kind": "node",
                    "name": "synthetic-node",
                    "data": {"state": "complete"},
                }
            ],
            "output": {"result": "synthetic"},
            "error": None,
        },
        "redaction": {
            "policy_version": "test-policy-1",
            "actions": [],
            "scan_result": "passed",
        },
    }
