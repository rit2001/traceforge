from __future__ import annotations

import copy
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from traceforge import cli
from traceforge.history import SQLiteReplayHistory
from traceforge.web import RunnerRegistrationError, create_app, load_builtin_example

ROOT = Path(__file__).resolve().parents[1]
RUNNERS = {
    "controlled-weather": "Weather Grounding",
    "rag-citation-grounding": "RAG Citation Grounding",
    "tool-argument-safety": "Tool Argument Safety",
}


def _payload(runner: str = "controlled-weather") -> dict:
    example = load_builtin_example(runner)
    return {"runner": runner, "source_mode": "example", **example}


def test_dashboard_metadata_empty_state_and_replay_history(tmp_path: Path) -> None:
    database = tmp_path / "history.sqlite3"
    client = TestClient(create_app(database))
    page = client.get("/")
    assert client.get("/healthz").json() == {"status": "ok"}
    assert "Ready when your evidence is." in page.text
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
    assert "changedExpected ? 'neutral' : 'bad'" in page
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
