from __future__ import annotations

import copy
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from scripts.create_workbench_review_data import (
    CAPTURE_ID as REVIEW_CAPTURE_ID,
)
from scripts.create_workbench_review_data import create_review_data
from traceforge import cli
from traceforge.assembly import SQLiteAssemblyState
from traceforge.history import SQLiteReplayHistory
from traceforge.kafka_runtime import capsule_events
from traceforge.sealing import seal_capsule
from traceforge.store import JsonFileCapsuleStore
from traceforge.web import RunnerRegistrationError, create_app, load_builtin_example
from traceforge.workbench import SQLiteRunCatalog

ROOT = Path(__file__).resolve().parents[1]
RUNNERS = {
    "controlled-weather": "Weather Grounding",
    "rag-citation-grounding": "RAG Citation Grounding",
    "tool-argument-safety": "Tool Argument Safety",
}


def test_nonexistent_assembly_database_is_read_only_and_not_created(tmp_path: Path) -> None:
    missing = tmp_path / "missing-assembly.sqlite3"
    catalog = SQLiteRunCatalog(missing)

    snapshot = catalog.snapshot()

    assert snapshot.source_dict() == {
        "state": "unavailable",
        "reason": "database-missing",
        "run_count": 0,
    }
    assert catalog.list() == []
    assert missing.exists() is False


def test_existing_assembly_database_is_opened_in_sqlite_read_only_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "empty-assembly.sqlite3"
    state = SQLiteAssemblyState(database, tmp_path / "capsules")
    state.close()
    real_connect = sqlite3.connect
    calls: list[tuple[str, bool]] = []

    def record_connect(target: str, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        calls.append((target, kwargs.get("uri") is True))
        return real_connect(target, *args, **kwargs)

    monkeypatch.setattr("traceforge.workbench.sqlite3.connect", record_connect)

    assert SQLiteRunCatalog(database).snapshot().source_state == "ready"
    assert calls == [(f"{database.resolve().as_uri()}?mode=ro", True)]


def test_catalog_distinguishes_unconfigured_missing_and_valid_empty_sources(
    tmp_path: Path,
) -> None:
    unconfigured = TestClient(create_app(tmp_path / "unconfigured-history.sqlite3"))
    missing_path = tmp_path / "missing-source.sqlite3"
    missing = TestClient(
        create_app(
            tmp_path / "missing-history.sqlite3",
            assembly_database=missing_path,
        )
    )
    empty_path = tmp_path / "empty-assembly.sqlite3"
    empty_state = SQLiteAssemblyState(empty_path, tmp_path / "empty-capsules")
    empty_state.close()
    empty = TestClient(
        create_app(
            tmp_path / "empty-history.sqlite3",
            assembly_database=empty_path,
        )
    )

    assert unconfigured.get("/api/run-source").json() == {
        "state": "not-configured",
        "reason": "not-configured",
        "run_count": 0,
    }
    assert missing.get("/api/run-source").json() == {
        "state": "unavailable",
        "reason": "database-missing",
        "run_count": 0,
    }
    assert empty.get("/api/run-source").json() == {
        "state": "ready",
        "reason": None,
        "run_count": 0,
    }
    assert "No capture database configured." in unconfigured.get("/").text
    missing_page = missing.get("/").text
    assert "Capture source unavailable." in missing_page
    assert str(missing_path) not in missing_page
    assert "No captured runs yet." in empty.get("/").text
    assert missing_path.exists() is False
    styles = (ROOT / "src/traceforge/static/dashboard.css").read_text()
    assert ".run-detail.is-empty { min-height: 0;" in styles
    assert ".catalog-empty { width: min(100%, 860px);" in styles


def test_controlled_review_data_generator_creates_one_replayable_run(tmp_path: Path) -> None:
    output = tmp_path / "workbench-review"

    paths = create_review_data(output)
    repeated = create_review_data(output)
    snapshot = SQLiteRunCatalog(
        paths.assembly_database,
        paths.capsule_directory,
    ).snapshot()
    detail = SQLiteRunCatalog(
        repeated.assembly_database,
        repeated.capsule_directory,
    ).get(REVIEW_CAPTURE_ID)

    assert paths == repeated
    assert snapshot.source_dict() == {"state": "ready", "reason": None, "run_count": 1}
    assert [run.run_id for run in snapshot.runs] == [REVIEW_CAPTURE_ID]
    assert detail is not None
    document = detail.to_dict()
    assert document["subject"] == "Agentic Chatbot — Controlled Demo"
    assert document["completed"] is True
    assert document["replayable"] is True
    assert document["evidence"] == {
        "state": "verified",
        "reason": None,
        "available": True,
        "sealed": True,
        "integrity_verified": True,
        "capsule_id": "controlled-agentic-review-v1",
        "schema_version": "0.2.0",
        "digest": document["evidence"]["digest"],
    }
    assert [(item["kind"], item["operation"]) for item in document["dependencies"]] == [
        ("model", "chat.completions"),
        ("tool", "web.search"),
        ("model", "chat.completions"),
    ]
    assert SQLiteReplayHistory(paths.history_database).recent() == []


def test_review_data_generator_refuses_repository_runtime_evidence(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside the repository"):
        create_review_data(ROOT / "generated-workbench-review")

    destination = tmp_path / "review-destination"
    destination.mkdir()
    link = tmp_path / "review-link"
    link.symlink_to(destination, target_is_directory=True)
    with pytest.raises(ValueError, match="cannot be a symlink"):
        create_review_data(link)

    assert not (ROOT / "controlled-agentic-review.json").exists()


def _payload(runner: str = "controlled-weather") -> dict:
    example = load_builtin_example(runner)
    return {"runner": runner, "source_mode": "example", **example}


def _capture_run(
    tmp_path: Path,
    *,
    capture_id: str,
    completed: bool = True,
) -> tuple[Path, Path | None]:
    database = tmp_path / f"{capture_id}-assembly.sqlite3"
    state = SQLiteAssemblyState(database, tmp_path / f"{capture_id}-capsules")
    events = capsule_events(load_builtin_example("controlled-weather")["capsule"], capture_id)
    capsule_path = None
    for event in events if completed else events[:1]:
        capsule_path = state.process(event).capsule_path or capsule_path
    state.close()
    return database, capsule_path


def _workbench_client(
    tmp_path: Path,
    assembly_database: Path,
    *,
    capsule_directory: Path | None = None,
) -> TestClient:
    return TestClient(
        create_app(
            tmp_path / "history.sqlite3",
            assembly_database=assembly_database,
            capsule_directory=capsule_directory,
        )
    )


def _capture_runs(tmp_path: Path, *capture_ids: str) -> tuple[Path, dict[str, Path]]:
    database = tmp_path / "shared-assembly.sqlite3"
    state = SQLiteAssemblyState(database, tmp_path / "shared-capsules")
    paths: dict[str, Path] = {}
    capsule = load_builtin_example("controlled-weather")["capsule"]
    for capture_id in capture_ids:
        for event in capsule_events(capsule, capture_id):
            result = state.process(event)
        assert result.capsule_path is not None
        paths[capture_id] = result.capsule_path
    state.close()
    return database, paths


def test_completed_capture_with_valid_capsule_appears_in_run_catalog(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="capture-valid")
    response = _workbench_client(tmp_path, assembly_database).get("/api/runs")

    assert response.status_code == 200
    assert response.json() == [
        {
            "run_id": "capture-valid",
            "completed": True,
            "replayable": True,
            "evidence_state": "verified",
            "capsule_id": "weather-kolkata-controlled-v0",
            "schema_version": "0.1.0",
            "subject": "controlled-weather-agent",
            "recorded_at": "2026-07-19T00:00:00Z",
            "trace_id": None,
            "span_id": None,
        }
    ]


def test_container_capsule_reference_resolves_from_trusted_host_root(tmp_path: Path) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="relocated-capture")
    assert capsule_path is not None
    container_path = "/data/capsules/relocated-capture.json"
    with sqlite3.connect(assembly_database) as connection:
        connection.execute(
            "UPDATE captures SET capsule_path=? WHERE capture_id=?",
            (container_path, "relocated-capture"),
        )

    detail = (
        _workbench_client(
            tmp_path,
            assembly_database,
            capsule_directory=capsule_path.parent,
        )
        .get("/api/runs/relocated-capture")
        .json()
    )

    assert detail["evidence"]["state"] == "verified"
    assert detail["evidence"]["integrity_verified"] is True
    assert detail["replayable"] is True
    assert container_path not in json.dumps(detail)
    assert str(capsule_path) not in json.dumps(detail)


def test_existing_recorded_capsule_path_takes_precedence_over_relocation_root(
    tmp_path: Path,
) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="direct-path")
    alternate_root = tmp_path / "alternate-capsules"
    alternate_root.mkdir()
    JsonFileCapsuleStore().save(
        alternate_root / "direct-path.json",
        load_builtin_example("rag-citation-grounding")["capsule"],
    )

    detail = (
        _workbench_client(
            tmp_path,
            assembly_database,
            capsule_directory=alternate_root,
        )
        .get("/api/runs/direct-path")
        .json()
    )

    assert detail["evidence"]["capsule_id"] == "weather-kolkata-controlled-v0"
    assert detail["subject"] == "controlled-weather-agent"


def test_browser_input_cannot_override_trusted_capsule_root(tmp_path: Path) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="configured-root")
    assert capsule_path is not None
    with sqlite3.connect(assembly_database) as connection:
        connection.execute(
            "UPDATE captures SET capsule_path=? WHERE capture_id=?",
            ("/data/capsules/configured-root.json", "configured-root"),
        )
    browser_root = tmp_path / "browser-selected-root"
    browser_root.mkdir()
    client = _workbench_client(
        tmp_path,
        assembly_database,
        capsule_directory=capsule_path.parent,
    )

    response = client.request(
        "GET",
        "/api/runs/configured-root",
        params={"capsule_directory": str(browser_root)},
        json={"capsule_directory": str(browser_root)},
    )

    assert response.status_code == 200
    assert response.json()["evidence"]["state"] == "verified"


def test_trusted_capsule_root_rejects_capture_id_traversal(tmp_path: Path) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="safe-capture")
    assert capsule_path is not None
    trusted_root = tmp_path / "trusted-root"
    trusted_root.mkdir()
    escaped = tmp_path / "escaped.json"
    escaped.write_bytes(capsule_path.read_bytes())
    with sqlite3.connect(assembly_database) as connection:
        connection.execute(
            "UPDATE captures SET capture_id=?, capsule_path=? WHERE capture_id=?",
            ("../escaped", "/data/capsules/../escaped.json", "safe-capture"),
        )

    runs = (
        _workbench_client(
            tmp_path,
            assembly_database,
            capsule_directory=trusted_root,
        )
        .get("/api/runs")
        .json()
    )

    assert runs == [
        {
            "run_id": "../escaped",
            "completed": True,
            "replayable": False,
            "evidence_state": "missing",
            "capsule_id": None,
            "schema_version": None,
            "subject": None,
            "recorded_at": None,
            "trace_id": None,
            "span_id": None,
        }
    ]


def test_trusted_capsule_root_rejects_symlink_escape(tmp_path: Path) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="symlink-capture")
    assert capsule_path is not None
    trusted_root = tmp_path / "trusted-root"
    trusted_root.mkdir()
    (trusted_root / "symlink-capture.json").symlink_to(capsule_path)
    with sqlite3.connect(assembly_database) as connection:
        connection.execute(
            "UPDATE captures SET capsule_path=? WHERE capture_id=?",
            ("/data/capsules/symlink-capture.json", "symlink-capture"),
        )

    detail = (
        _workbench_client(
            tmp_path,
            assembly_database,
            capsule_directory=trusted_root,
        )
        .get("/api/runs/symlink-capture")
        .json()
    )

    assert detail["evidence"]["state"] == "missing"
    assert detail["replayable"] is False


def test_relocated_missing_and_tampered_evidence_remain_unavailable(tmp_path: Path) -> None:
    assembly_database, paths = _capture_runs(tmp_path, "relocated-missing", "relocated-invalid")
    with sqlite3.connect(assembly_database) as connection:
        for capture_id in paths:
            connection.execute(
                "UPDATE captures SET capsule_path=? WHERE capture_id=?",
                (f"/data/capsules/{capture_id}.json", capture_id),
            )
    paths["relocated-missing"].unlink()
    capsule = json.loads(paths["relocated-invalid"].read_text(encoding="utf-8"))
    capsule["invocation"]["input"] = {"tampered": True}
    paths["relocated-invalid"].write_text(json.dumps(capsule), encoding="utf-8")

    runs = (
        _workbench_client(
            tmp_path,
            assembly_database,
            capsule_directory=paths["relocated-invalid"].parent,
        )
        .get("/api/runs")
        .json()
    )

    states = {run["run_id"]: run["evidence_state"] for run in runs}
    assert states == {"relocated-invalid": "invalid", "relocated-missing": "missing"}


def test_run_detail_returns_ordered_generic_dependencies(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="capture-detail")
    response = _workbench_client(tmp_path, assembly_database).get("/api/runs/capture-detail")

    assert response.status_code == 200
    detail = response.json()
    assert [item["sequence"] for item in detail["dependencies"]] == [1, 2, 3]
    assert [item["kind"] for item in detail["dependencies"]] == ["model", "http", "http"]
    assert detail["invocation"]["operation"] == "answer_weather_question"
    assert detail["original_execution"]["status"] == "completed"
    assert detail["original_execution"]["events"][0]["sequence"] == 1
    assert detail["evidence"] == {
        "state": "verified",
        "reason": None,
        "available": True,
        "sealed": True,
        "integrity_verified": True,
        "capsule_id": "weather-kolkata-controlled-v0",
        "schema_version": "0.1.0",
        "digest": detail["evidence"]["digest"],
    }
    assert detail["evidence"]["digest"].startswith("sha256:")


def test_incomplete_capture_is_not_replayable(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="capture-incomplete", completed=False)
    client = _workbench_client(tmp_path, assembly_database)

    summary = client.get("/api/runs").json()[0]
    detail = client.get("/api/runs/capture-incomplete").json()
    assert summary["completed"] is False
    assert summary["replayable"] is False
    assert summary["evidence_state"] == "pending"
    assert detail["evidence"]["reason"] == "capture-incomplete"
    assert detail["original_execution"] is None


def test_completed_capture_with_missing_capsule_is_explicit(tmp_path: Path) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="capture-missing")
    assert capsule_path is not None
    capsule_path.unlink()

    detail = _workbench_client(tmp_path, assembly_database).get("/api/runs/capture-missing").json()
    assert detail["completed"] is True
    assert detail["replayable"] is False
    assert detail["evidence"]["state"] == "missing"
    assert detail["evidence"]["reason"] == "capsule-file-missing"
    assert "path" not in detail["evidence"]


def test_tampered_capsule_is_invalid_and_not_replayable(tmp_path: Path) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="capture-invalid")
    assert capsule_path is not None
    capsule = json.loads(capsule_path.read_text(encoding="utf-8"))
    capsule["invocation"]["input"] = {"tampered": True}
    capsule_path.write_text(json.dumps(capsule), encoding="utf-8")

    detail = _workbench_client(tmp_path, assembly_database).get("/api/runs/capture-invalid").json()
    assert detail["replayable"] is False
    assert detail["evidence"]["state"] == "invalid"
    assert detail["evidence"]["reason"] == "validation-failed"
    assert detail["evidence"]["integrity_verified"] is False
    assert detail["invocation"] is None


@pytest.mark.parametrize(
    ("contents", "encoding"),
    [
        pytest.param(b"{", "utf-8", id="malformed-json"),
        pytest.param(b"{}", "utf-8", id="structurally-invalid"),
        pytest.param(b"\xff", None, id="invalid-utf8"),
    ],
)
def test_unreadable_or_invalid_capsule_isolated_from_other_runs(
    tmp_path: Path, contents: bytes, encoding: str | None
) -> None:
    assembly_database, paths = _capture_runs(tmp_path, "bad-run", "good-run")
    if encoding is None:
        paths["bad-run"].write_bytes(contents)
    else:
        paths["bad-run"].write_text(contents.decode(encoding), encoding=encoding)

    response = _workbench_client(tmp_path, assembly_database).get("/api/runs")

    assert response.status_code == 200
    runs = {item["run_id"]: item for item in response.json()}
    assert runs["bad-run"]["evidence_state"] == "invalid"
    assert runs["bad-run"]["replayable"] is False
    assert runs["good-run"]["evidence_state"] == "verified"
    assert runs["good-run"]["replayable"] is True


def test_valid_capsule_with_unsupported_recorded_error_is_verified_but_unreplayable(
    tmp_path: Path, capsule_draft: dict[str, Any]
) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="unreplayable-run")
    assert capsule_path is not None
    draft = copy.deepcopy(capsule_draft)
    draft["schema_version"] = "0.2.0"
    draft["dependencies"][0] = {
        "dependency_id": "dependency-1",
        "sequence": 1,
        "kind": "tool",
        "operation": "catalog.lookup",
        "request": {"arguments": {"item_id": 1}},
        "outcome": {
            "status": "errored",
            "error": {
                "type": "ValueError",
                "message": "unsupported recorded failure",
                "data": None,
            },
        },
        "duration_ms": 1,
    }
    JsonFileCapsuleStore().save(capsule_path, seal_capsule(draft))

    detail = _workbench_client(tmp_path, assembly_database).get("/api/runs/unreplayable-run").json()

    assert detail["completed"] is True
    assert detail["evidence"]["state"] == "verified"
    assert detail["evidence"]["integrity_verified"] is True
    assert detail["evidence"]["reason"] == "unsupported-recorded-error"
    assert detail["replayable"] is False


def test_unknown_run_id_returns_precise_404(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="known-run", completed=False)
    response = _workbench_client(tmp_path, assembly_database).get("/api/runs/unknown-run")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run-not-found"


def test_replay_history_does_not_create_original_runs(tmp_path: Path) -> None:
    history_database = tmp_path / "history.sqlite3"
    SQLiteReplayHistory(history_database).append(
        capsule_digest="sha256:history-only",
        runner="controlled-weather",
        technical_result="completed",
        behavioural_result="passed",
        error_summary=None,
    )
    client = TestClient(
        create_app(history_database, assembly_database=tmp_path / "absent-assembly.sqlite3")
    )

    assert len(client.get("/api/history").json()) == 1
    assert client.get("/api/runs").json() == []


def test_replay_history_id_cannot_become_original_run_identity(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="1", completed=False)
    history_database = tmp_path / "history.sqlite3"
    SQLiteReplayHistory(history_database).append(
        capsule_digest="sha256:unrelated",
        runner="controlled-weather",
        technical_result="completed",
        behavioural_result="passed",
        error_summary=None,
    )
    client = TestClient(create_app(history_database, assembly_database=assembly_database))

    assert client.get("/api/history").json()[0]["id"] == 1
    run = client.get("/api/runs/1").json()
    assert run["run_id"] == "1"
    assert run["completed"] is False
    assert run["evidence"]["state"] == "pending"


def test_run_read_api_does_not_accept_browser_filesystem_paths(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="catalogued", completed=False)
    outside_capsule = tmp_path / "browser-selected.json"
    outside_capsule.write_text(
        json.dumps(load_builtin_example("controlled-weather")["capsule"]), encoding="utf-8"
    )
    client = _workbench_client(tmp_path, assembly_database)

    response = client.get(
        "/api/runs/not-catalogued",
        params={
            "capsule_path": str(outside_capsule),
            "assembly_database": str(tmp_path / "other.sqlite3"),
            "runner": "arbitrary.module:run",
        },
    )
    assert response.status_code == 404
    ordinary = client.get("/api/runs").json()
    attempted = client.get(
        "/api/runs",
        params={
            "capsule_path": str(outside_capsule),
            "assembly_database": str(tmp_path / "other.sqlite3"),
        },
    ).json()
    assert attempted == ordinary
    ordinary_source = client.get("/api/run-source").json()
    attempted_source = client.get(
        "/api/run-source",
        params={
            "capsule_directory": str(tmp_path / "other-capsules"),
            "assembly_database": str(tmp_path / "other.sqlite3"),
        },
    ).json()
    assert attempted_source == ordinary_source


def test_run_api_never_exposes_capsule_filesystem_reference(tmp_path: Path) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="no-path-leak")
    assert capsule_path is not None
    client = _workbench_client(tmp_path, assembly_database)

    responses = [client.get("/api/runs").json(), client.get("/api/runs/no-path-leak").json()]
    for response in responses:
        serialized = json.dumps(response, sort_keys=True)
        assert str(capsule_path) not in serialized
        assert "capsule_path" not in serialized


def test_completed_capture_without_capsule_reference_is_explicit(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="missing-reference")
    with sqlite3.connect(assembly_database) as connection:
        connection.execute(
            "UPDATE captures SET capsule_path=NULL WHERE capture_id=?", ("missing-reference",)
        )

    detail = (
        _workbench_client(tmp_path, assembly_database).get("/api/runs/missing-reference").json()
    )

    assert detail["completed"] is True
    assert detail["replayable"] is False
    assert detail["evidence"]["state"] == "missing"
    assert detail["evidence"]["reason"] == "capsule-reference-missing"


def test_workbench_read_model_remains_framework_neutral(tmp_path: Path) -> None:
    core_surfaces = [
        ROOT / "src/traceforge/workbench.py",
        ROOT / "src/traceforge/templates/dashboard.html",
        ROOT / "src/traceforge/static/dashboard.css",
    ]
    prohibited = (
        "langgraph",
        "langchain",
        "crewai",
        "stategraph",
        "state graph",
        "toolmessage",
        "aimessage",
        "agent node",
        "supervisor",
        "planner",
    )
    for path in core_surfaces:
        source = path.read_text(encoding="utf-8").lower()
        assert all(token not in source for token in prohibited)

    assembly_database, _ = _capture_run(tmp_path, capture_id="generic-run")
    detail = _workbench_client(tmp_path, assembly_database).get("/api/runs/generic-run").json()
    assert not ({"nodes", "agents", "graph", "messages"} & detail.keys())


def test_run_detail_ui_uses_real_catalog_data_and_forensics_hierarchy(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="capture-ui")
    client = _workbench_client(tmp_path, assembly_database)
    page = client.get("/").text
    detail = client.get("/api/runs/capture-ui").json()

    assert 'data-run-id="capture-ui"' in page
    assert 'data-full-run-id="capture-ui"' in page
    assert "Execution Forensics" in page
    assert "Execution Map" in page
    assert "Dependencies" in page
    assert "Execution Step Detail" in page
    assert "Run Information" in page
    assert "Replay &amp; Regression Summary" in page
    assert "Structured Diff" in page
    assert "Evidence &amp; Immutable Record" in page
    assert 'class="forensics-grid"' in page
    assert "className = 'execution-node'" in page
    assert detail["evidence"]["capsule_id"] == "weather-kolkata-controlled-v0"
    assert detail["evidence"]["schema_version"] == "0.1.0"
    assert "1.0.0" not in page
    assert "Share" not in page
    assert "New Run" not in page
    assert "Projects" not in page
    assert "Preflight" not in page


def test_run_detail_uses_short_display_id_but_retains_canonical_id(tmp_path: Path) -> None:
    run_id = "gateway-otel-smoke-0123456789abcdef"
    assembly_database, _ = _capture_run(tmp_path, capture_id=run_id)

    page = _workbench_client(tmp_path, assembly_database).get("/").text

    assert f'data-full-run-id="{run_id}"' in page
    assert f'title="{run_id}"' in page
    assert "gateway-ot…9abcdef" in page
    assert "const shortId" in page


def test_missing_evidence_uses_compact_truthful_execution_state(tmp_path: Path) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="missing-ui")
    assert capsule_path is not None
    capsule_path.unlink()
    client = _workbench_client(tmp_path, assembly_database)

    detail = client.get("/api/runs/missing-ui").json()
    page = client.get("/").text

    assert detail["evidence"]["state"] == "missing"
    assert detail["dependencies"] == []
    assert "No execution boundary records are available." in page
    assert "compact-empty" in page
    assert 'id="header-capsule"' not in page


def test_run_replay_and_attempts_are_separate_reachable_views(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="separate-views")
    page = _workbench_client(tmp_path, assembly_database).get("/").text
    run_markup = page.split('<section id="replay-view"', maxsplit=1)[0]

    assert 'data-view-target="run-view"' in page
    assert 'data-view-target="replay-view"' in page
    assert 'data-view-target="attempts-view"' in page
    assert "'run-view': '#runs'" in page
    assert "'replay-view': '#replay'" in page
    assert "'attempts-view': '#attempts'" in page
    assert "window.addEventListener('hashchange', syncViewFromHash)" in page
    assert "window.history.replaceState(null, '', '#runs')" in page
    assert 'id="replay-view" class="app-view"' in page
    assert 'id="attempts-view" class="app-view"' in page
    assert "Zero live fallback" not in run_markup
    assert "Zero live fallback" in page
    assert '<details class="forensics-section evidence-record">' in page
    assert '<details class="forensics-section evidence-record" open' not in page


def test_run_detail_preserves_four_independent_replay_states(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="four-replay-states")
    page = _workbench_client(tmp_path, assembly_database).get("/").text

    assert "summary('Technical replay', 'Not run'" in page
    assert "summary('Deterministic match', 'No result'" in page
    assert "summary('Structured diff', 'No result'" in page
    assert "summary('Regression', 'Not evaluated'" in page


def test_recorded_sub_millisecond_timing_is_not_presented_as_fake_zero(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="truthful-timing")
    page = _workbench_client(tmp_path, assembly_database).get("/").text

    assert "const formatDuration" in page
    assert "value === 0 ? '<1 ms'" in page
    assert "if (duration) footer.append(text('time', duration))" in page
    assert "if (duration) button.append(text('time', duration))" in page
    assert "duration ? ` · ${duration}` : ''" in page
    assert "duration_ms || 0" not in page
    assert "duration_ms ?? 0" not in page


def test_selected_step_inspector_has_accessible_evidence_tabs(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="inspector-tabs")
    page = _workbench_client(tmp_path, assembly_database).get("/").text
    styles = (ROOT / "src/traceforge/static/dashboard.css").read_text()

    assert 'class="inspector-tabs" role="tablist"' in page
    assert 'data-inspector-tab="overview"' in page
    assert 'data-inspector-tab="request"' in page
    assert 'data-inspector-tab="response"' in page
    assert 'data-inspector-tab="raw"' in page
    assert 'role="tabpanel"' in page
    assert "ArrowLeft" in page
    assert "ArrowRight" in page
    assert '.inspector-tabs button[aria-selected="true"]' in styles
    assert ".dependency-record > button" in styles
    assert ".execution-node-heading" in styles


def test_replay_attempts_empty_state_navigates_to_real_replay_lab(tmp_path: Path) -> None:
    page = TestClient(create_app(tmp_path / "history.sqlite3")).get("/").text

    assert "No replay attempts yet." in page
    assert 'data-open-replay="true"' in page
    assert "navigateToView('replay-view')" in page


def test_replay_lab_pre_result_layout_is_compact_and_truthful(tmp_path: Path) -> None:
    page = TestClient(create_app(tmp_path / "history.sqlite3")).get("/").text
    styles = (ROOT / "src/traceforge/static/dashboard.css").read_text()

    assert 'class="workbench is-preflight"' in page
    assert "expandReplayReport()" in page
    assert ".workbench.is-preflight" in styles
    assert ".workbench.is-preflight .result-state" in styles
    assert '<details class="project-callout">' in page
    assert '<details class="project-callout" open' not in page
    assert 'placeholder="Paste a complete sealed Replay Capsule JSON object"' in page
    assert 'placeholder="Paste a developer-approved regression specification"' in page
    assert 'placeholder=\'{ "schema_version": "0.1.0"' not in page


def test_successful_replay_ui_exposes_real_diff_and_regression_records(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "history.sqlite3"))
    response = client.post("/api/replay", json=_payload())
    page = client.get("/").text

    assert response.status_code == 200
    assert response.json()["execution_diff"]["differences"]
    assert response.json()["regression"]["assertions"]
    assert "ExecutionDiff" in page
    assert "difference.code" in page
    assert "difference.section" in page
    assert "formatSnapshot(difference.expected)" in page
    assert "formatSnapshot(difference.actual)" in page
    assert "data.regression?.assertions" in page
    assert "assertion.expected" in page
    assert "assertion.actual" in page


def test_existing_replay_endpoint_contract_is_unchanged_with_run_catalog(tmp_path: Path) -> None:
    assembly_database, _ = _capture_run(tmp_path, capture_id="capture-for-replay")
    response = _workbench_client(tmp_path, assembly_database).post("/api/replay", json=_payload())

    assert response.status_code == 200
    assert response.json()["technical_status"] == "completed"
    assert response.json()["execution_diff"]["matches"] is False
    assert response.json()["regression"]["passed"] is True


def test_dashboard_metadata_empty_state_and_replay_history(tmp_path: Path) -> None:
    database = tmp_path / "history.sqlite3"
    client = TestClient(create_app(database))
    page = client.get("/")
    assert client.get("/healthz").json() == {"status": "ok"}
    assert "Report appears after replay." in page.text
    for runner_id, name in RUNNERS.items():
        assert runner_id in page.text
        assert name in page.text
    assert 'role="radiogroup"' in page.text

    response = client.post("/api/replay", json=_payload())
    assert response.status_code == 200
    assert response.json()["technical_status"] == "completed"
    assert response.json()["regression"]["passed"] is True
    history = SQLiteReplayHistory(database).recent()
    assert len(history) == 1
    assert history[0].capsule_digest.startswith("sha256:")
    assert history[0].behavioural_result == "passed"
    history_page = client.get("/").text
    assert "Select runner" in history_page
    assert "Replay again" not in history_page


def test_attempts_navigation_refreshes_authoritative_history_without_page_reload(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "history.sqlite3"))
    initially_loaded_page = client.get("/").text

    assert client.get("/api/history").json() == []
    assert "No replay attempts yet." in initially_loaded_page

    response = client.post("/api/replay", json=_payload())

    assert response.status_code == 200
    fresh_history = client.get("/api/history").json()
    assert len(fresh_history) == 1
    assert fresh_history[0]["technical_result"] == "completed"
    assert "const refreshHistory = async ()" in initially_loaded_page
    assert "await fetch('/api/history')" in initially_loaded_page
    assert "viewId === 'attempts-view'" in initially_loaded_page
    assert "void refreshHistory()" in initially_loaded_page
    assert "renderHistory(await response.json())" in initially_loaded_page


@pytest.mark.parametrize("runner_id", RUNNERS)
def test_each_builtin_example_is_loadable_and_replays(tmp_path: Path, runner_id: str) -> None:
    client = TestClient(create_app(tmp_path / "history.sqlite3"))
    example = client.get(f"/api/examples/{runner_id}")
    assert example.status_code == 200
    response = client.post(
        "/api/replay", json={"runner": runner_id, "source_mode": "example", **example.json()}
    )
    assert response.status_code == 200
    assert response.json()["regression"]["passed"] is True


def test_dashboard_modes_reject_ambiguous_or_missing_evidence(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "history.sqlite3"))
    ambiguous = _payload()
    ambiguous["source_mode"] = "upload,paste"
    response = client.post("/api/replay", json=ambiguous)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ambiguous-input"

    response = client.post(
        "/api/replay", json={"runner": "controlled-weather", "source_mode": "upload"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing-evidence"


@pytest.mark.parametrize("mode", ["upload", "paste"])
def test_dashboard_accepts_one_explicit_upload_or_paste_mode(tmp_path: Path, mode: str) -> None:
    client = TestClient(create_app(tmp_path / "history.sqlite3"))
    payload = _payload()
    payload["source_mode"] = mode
    response = client.post("/api/replay", json=payload)
    assert response.status_code == 200
    assert response.json()["regression"]["passed"] is True


def test_dashboard_rejects_invalid_json_tampering_unknown_runner_and_oversize(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "history.sqlite3"))
    invalid = client.post("/api/replay", content=b"{", headers={"content-type": "application/json"})
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid-json"

    unknown = _payload()
    unknown["runner"] = "arbitrary.module:run"
    response = client.post("/api/replay", json=unknown)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "runner-not-registered"
    page = client.get("/").text
    assert "arbitrary.module:run" not in page

    tampered = _payload()
    tampered["capsule"]["invocation"]["input"] = {"tampered": True}
    response = client.post("/api/replay", json=tampered)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "capsule-integrity"

    limited = TestClient(create_app(tmp_path / "limited-history.sqlite3", max_upload_bytes=20))
    oversized = limited.post("/api/replay", content=b"{" + b"x" * 30 + b"}")
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "upload-too-large"


def test_cross_scenario_mismatch_and_regression_failure_are_not_green(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "history.sqlite3"))
    mismatch = _payload("controlled-weather")
    mismatch["runner"] = "rag-citation-grounding"
    response = client.post("/api/replay", json=mismatch)
    assert response.status_code == 400
    assert response.json()["error"]["code"] in {"dependency-mismatch", "trusted-runner-failure"}

    failed = _payload()
    failed["spec"] = copy.deepcopy(failed["spec"])
    failed["spec"]["assertions"][0]["expected"] = "not the replay result"
    response = client.post("/api/replay", json=failed)
    assert response.status_code == 200
    assert response.json()["technical_status"] == "completed"
    assert response.json()["regression"]["passed"] is False
    history_page = client.get("/").text
    assert 'class="attempt-status bad">errored' in history_page
    assert 'class="attempt-verdict bad">failed' in history_page


def test_dashboard_template_uses_safe_rendering_and_semantic_state_hooks(tmp_path: Path) -> None:
    page = TestClient(create_app(tmp_path / "history.sqlite3")).get("/").text
    assert "innerHTML" not in page
    assert "aria-live" in page
    assert all(
        state in page for state in ("empty-state", "loading-state", "success-state", "error-state")
    )
    assert "prefers-reduced-motion" in (ROOT / "src/traceforge/static/dashboard.css").read_text()
    assert "@media (max-width: 860px)" in (ROOT / "src/traceforge/static/dashboard.css").read_text()


def test_dashboard_communicates_trusted_project_connection_and_evidence_boundary(
    tmp_path: Path,
) -> None:
    page = TestClient(create_app(tmp_path / "history.sqlite3")).get("/").text
    assert "Connect your project" in page
    assert "reviewed built-in demonstrations" in page
    assert "traceforge serve" in page
    assert "my-agent=my_project.traceforge_runner:run" in page
    assert "registered custom runners appear automatically" in page
    assert "they are never executed from browser uploads" in page
    assert 'name="runner"' not in page
    assert 'type="file"' in page


def test_dashboard_uses_neutral_expected_repair_and_collapsed_raw_evidence(tmp_path: Path) -> None:
    page = TestClient(create_app(tmp_path / "history.sqlite3")).get("/").text
    styles = (ROOT / "src/traceforge/static/dashboard.css").read_text()
    assert "Changed — expected repair" in page
    assert "data.comparison?.deterministic_match ? 'good' : 'neutral'" in page
    assert "satisfies the approved regression" in page
    assert "summary-card.neutral" in styles
    assert "summary-card.bad" in styles
    assert "details('Original observation'" in page
    assert "details('Replay observation'" in page
    assert "details('Raw dependency payloads'" in page
    assert "<details open" not in page


def test_custom_runner_registration_uses_serve_startup_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = tmp_path / "trusted_runner.py"
    module.write_text("from traceforge.examples.weather_agent import run\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    captured: dict[str, Any] = {}
    monkeypatch.setitem(
        sys.modules,
        "uvicorn",
        SimpleNamespace(run=lambda app, **kwargs: captured.update(app=app, kwargs=kwargs)),
    )
    monkeypatch.setattr("traceforge.observability.configure", lambda _: None)
    monkeypatch.setattr("traceforge.observability.shutdown", lambda _: None)

    assert cli.main(["serve", "--runner", "my-agent=trusted_runner:run"]) == 0
    client = TestClient(captured["app"])
    assert "my-agent" in client.get("/").text
    assert client.get("/api/examples/my-agent").status_code == 404
    custom_payload = _payload()
    custom_payload.update(runner="my-agent", source_mode="upload")
    response = client.post("/api/replay", json=custom_payload)
    assert response.status_code == 200
    assert response.json()["regression"]["passed"] is True


def test_serve_wires_trusted_assembly_database_at_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="served-run")
    assert capsule_path is not None
    with sqlite3.connect(assembly_database) as connection:
        connection.execute(
            "UPDATE captures SET capsule_path=? WHERE capture_id=?",
            ("/data/capsules/served-run.json", "served-run"),
        )
    captured: dict[str, Any] = {}
    monkeypatch.setitem(
        sys.modules,
        "uvicorn",
        SimpleNamespace(run=lambda app, **kwargs: captured.update(app=app, kwargs=kwargs)),
    )
    monkeypatch.setattr("traceforge.observability.configure", lambda _: None)
    monkeypatch.setattr("traceforge.observability.shutdown", lambda _: None)

    assert (
        cli.main(
            [
                "serve",
                "--assembly-database",
                str(assembly_database),
                "--capsule-directory",
                str(capsule_path.parent),
            ]
        )
        == 0
    )
    runs = TestClient(captured["app"]).get("/api/runs").json()
    assert [(item["run_id"], item["evidence_state"]) for item in runs] == [
        ("served-run", "verified")
    ]


def test_serve_reads_trusted_catalog_paths_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assembly_database, capsule_path = _capture_run(tmp_path, capture_id="environment-run")
    assert capsule_path is not None
    with sqlite3.connect(assembly_database) as connection:
        connection.execute(
            "UPDATE captures SET capsule_path=? WHERE capture_id=?",
            ("/data/capsules/environment-run.json", "environment-run"),
        )
    captured: dict[str, Any] = {}
    monkeypatch.setenv("TRACEFORGE_ASSEMBLY_PATH", str(assembly_database))
    monkeypatch.setenv("TRACEFORGE_CAPSULE_DIRECTORY", str(capsule_path.parent))
    monkeypatch.setitem(
        sys.modules,
        "uvicorn",
        SimpleNamespace(run=lambda app, **kwargs: captured.update(app=app, kwargs=kwargs)),
    )
    monkeypatch.setattr("traceforge.observability.configure", lambda _: None)
    monkeypatch.setattr("traceforge.observability.shutdown", lambda _: None)

    assert cli.main(["serve"]) == 0
    detail = TestClient(captured["app"]).get("/api/runs/environment-run").json()
    assert detail["evidence"]["state"] == "verified"
    assert detail["replayable"] is True


@pytest.mark.parametrize(
    "registration",
    [
        "controlled-weather=trusted_runner:run",
        "missing-equals",
        "Bad_ID=trusted_runner:run",
        "bad-target=trusted_runner.run",
        "missing=does_not_exist:run",
        "not-callable=trusted_runner:__name__",
    ],
)
def test_custom_runner_registration_failures_are_precise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, registration: str
) -> None:
    module = tmp_path / "trusted_runner.py"
    module.write_text("from traceforge.examples.weather_agent import run\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(RunnerRegistrationError):
        create_app(tmp_path / "history.sqlite3", runner_registrations=[registration])


def test_duplicate_custom_registration_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = tmp_path / "trusted_runner.py"
    module.write_text("from traceforge.examples.weather_agent import run\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(RunnerRegistrationError, match="already registered"):
        create_app(
            tmp_path / "history.sqlite3",
            runner_registrations=["my-agent=trusted_runner:run", "my-agent=trusted_runner:run"],
        )
