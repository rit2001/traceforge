from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from traceforge.history import SQLiteReplayHistory
from traceforge.web import create_app

ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict:
    return {
        "runner": "controlled-weather",
        "capsule": json.loads((ROOT / "examples/weather/replay-capsule.json").read_text()),
        "spec": json.loads((ROOT / "examples/weather/regression-spec.json").read_text()),
    }


def test_dashboard_health_empty_state_and_replay_history(tmp_path: Path) -> None:
    database = tmp_path / "history.sqlite3"
    client = TestClient(create_app(database))
    assert client.get("/healthz").json() == {"status": "ok"}
    assert "No local replays yet" in client.get("/").text

    response = client.post("/api/replay", json=_payload())
    assert response.status_code == 200
    assert response.json()["regression"]["passed"] is True
    history = SQLiteReplayHistory(database).recent()
    assert len(history) == 1
    assert history[0].capsule_digest.startswith("sha256:")
    assert history[0].behavioural_result == "passed"


def test_dashboard_rejects_unregistered_runner_and_tampering(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "history.sqlite3"))
    payload = _payload()
    payload["runner"] = "arbitrary.module:run"
    assert client.post("/api/replay", json=payload).status_code == 400

    payload = _payload()
    payload["capsule"]["invocation"]["input"] = {"tampered": True}
    response = client.post("/api/replay", json=payload)
    assert response.status_code == 400
    assert "integrity.digest" in response.json()["error"]


def test_dashboard_upload_limit(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "history.sqlite3", max_upload_bytes=20))
    response = client.post(
        "/api/replay", content=b"{" + b"x" * 30 + b"}", headers={"content-type": "application/json"}
    )
    assert response.status_code == 413
