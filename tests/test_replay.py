from __future__ import annotations

import copy
import socket
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from traceforge.dependencies import RecordedDependencyAdapter
from traceforge.diff import ExecutionDiff
from traceforge.divergence import DivergenceAnalysis
from traceforge.examples.weather_agent import run as weather_runner
from traceforge.exceptions import (
    DependencyMismatchError,
    IntegrityError,
    LiveDependencyBlockedError,
    MissingDependencyError,
    SemanticValidationError,
    UnexpectedDependencyError,
)
from traceforge.interfaces import DependencyAdapter
from traceforge.regression import evaluate_regression
from traceforge.replay import CallableFrameworkAdapter, ReplayResult, replay_exact
from traceforge.sealing import seal_capsule
from traceforge.store import JsonFileCapsuleStore

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WEATHER_CAPSULE = REPOSITORY_ROOT / "examples" / "weather" / "replay-capsule.json"
WEATHER_SPEC = REPOSITORY_ROOT / "examples" / "weather" / "regression-spec.json"


def _weather_artifacts() -> tuple[dict[str, Any], dict[str, Any]]:
    store = JsonFileCapsuleStore()
    return store.load(WEATHER_CAPSULE), store.load(WEATHER_SPEC)


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _reject_completed_analysis(monkeypatch: pytest.MonkeyPatch) -> Mock:
    analysis = Mock(
        side_effect=AssertionError("technical replay failure cannot produce divergence analysis")
    )
    monkeypatch.setattr("traceforge.replay._analyze_exact_replay_divergence", analysis)
    return analysis


def test_successful_exact_replay_and_behavioural_pass() -> None:
    capsule, spec = _weather_artifacts()

    result = replay_exact(capsule, CallableFrameworkAdapter(weather_runner), spec)

    assert result.technical_status == "completed"
    assert result.deterministic_match is False
    assert result.replay_observation["output"]["umbrella_needed"] is True
    assert result.regression is not None and result.regression.passed


def test_replay_result_preserves_pre_execution_diff_constructor_shape() -> None:
    original_observation = {
        "execution_status": "completed",
        "events": [],
        "output": {"result": "original"},
        "error": None,
    }
    replay_observation = copy.deepcopy(original_observation)

    result = ReplayResult(
        "completed",
        original_observation,
        replay_observation,
        True,
        None,
    )

    assert result.execution_diff is None
    assert result.to_dict() == {
        "technical_status": "completed",
        "original_observation": original_observation,
        "replay_observation": replay_observation,
        "comparison": {
            "deterministic_match": True,
            "ignored_fields": [
                "duration_ms",
                "finished_at",
                "recorded_at",
                "started_at",
                "timestamp",
            ],
        },
        "regression": None,
        "execution_diff": None,
        "divergence_analysis": None,
    }


def test_successful_exact_replay_adds_structured_diff_without_changing_existing_fields(
    capsule_draft: dict[str, Any],
) -> None:
    capsule = seal_capsule(capsule_draft)
    capsule_before = copy.deepcopy(capsule)
    regression_spec = {
        "version": "0.1.0",
        "assertions": [{"path": "output.result", "operator": "equals", "expected": "synthetic"}],
    }
    regression_before = copy.deepcopy(regression_spec)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        recorded = capsule["dependencies"][0]
        dependencies.invoke(recorded["kind"], recorded["operation"], recorded["request"])
        return copy.deepcopy(capsule["original_observation"])

    result = replay_exact(capsule, CallableFrameworkAdapter(runner), regression_spec)
    document = result.to_dict()

    assert isinstance(result.execution_diff, ExecutionDiff)
    assert isinstance(result.divergence_analysis, DivergenceAnalysis)
    assert result.execution_diff.to_dict()["matches"] is True
    assert result.technical_status == "completed"
    assert result.original_observation == capsule_before["original_observation"]
    assert result.replay_observation == capsule_before["original_observation"]
    assert result.deterministic_match is True
    assert result.regression is not None and result.regression.passed is True
    assert document["technical_status"] == "completed"
    assert document["original_observation"] == capsule_before["original_observation"]
    assert document["replay_observation"] == capsule_before["original_observation"]
    assert document["comparison"] == {
        "deterministic_match": True,
        "ignored_fields": [
            "duration_ms",
            "finished_at",
            "recorded_at",
            "started_at",
            "timestamp",
        ],
    }
    assert document["regression"] == result.regression.to_dict()
    assert document["execution_diff"] == result.execution_diff.to_dict()
    assert document["divergence_analysis"] == result.divergence_analysis.to_dict()
    assert document["divergence_analysis"]["evidence_context"] == {
        "recorded_dependencies_reproduced": True,
        "replay_completed_technically": True,
    }
    assert document["divergence_analysis"]["findings"] == [
        "recorded_dependencies_reproduced",
        "no_semantic_divergence",
    ]
    assert document["divergence_analysis"]["matches"] is True
    assert all(
        domain["matches"] and domain["first_path"] is None
        for domain in document["divergence_analysis"]["domains"].values()
    )
    assert "regression" not in document["execution_diff"]
    assert _contains_key(document["execution_diff"], "assertions") is False
    assert capsule == capsule_before
    assert regression_spec == regression_before


def test_successful_replay_observation_divergence_has_nonmatching_structured_diff(
    capsule_draft: dict[str, Any],
) -> None:
    capsule = seal_capsule(capsule_draft)
    capsule_before = copy.deepcopy(capsule)
    regression_spec = {
        "version": "0.1.0",
        "assertions": [{"path": "execution_status", "operator": "equals", "expected": "completed"}],
    }

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        recorded = capsule["dependencies"][0]
        dependencies.invoke(recorded["kind"], recorded["operation"], recorded["request"])
        observation = copy.deepcopy(capsule["original_observation"])
        observation["output"]["result"] = "changed during replay"
        return observation

    result = replay_exact(capsule, CallableFrameworkAdapter(runner), regression_spec)
    execution_diff = result.execution_diff.to_dict()
    divergence_analysis = result.divergence_analysis.to_dict()

    assert result.technical_status == "completed"
    assert result.deterministic_match is False
    assert execution_diff["matches"] is False
    assert execution_diff["sections"]["dependencies"]["matches"] is True
    assert execution_diff["sections"]["terminal"]["matches"] is False
    assert execution_diff["first_divergences"]["terminal"] == "/output/result"
    assert [
        (difference["section"], difference["code"], difference["path"])
        for difference in execution_diff["differences"]
    ] == [("terminal", "value_changed", "/output/result")]
    assert result.regression is not None and result.regression.passed is True
    assert divergence_analysis["findings"] == [
        "recorded_dependencies_reproduced",
        "terminal_output_diverged",
    ]
    assert divergence_analysis["domains"]["terminal"]["first_path"] == "/output/result"
    assert divergence_analysis["evidence_context"] == {
        "recorded_dependencies_reproduced": True,
        "replay_completed_technically": True,
    }
    assert capsule == capsule_before


def test_dependency_mismatch_remains_a_technical_replay_failure_without_result(
    capsule_draft: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capsule = seal_capsule(capsule_draft)
    completed_result = None
    analysis = _reject_completed_analysis(monkeypatch)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        recorded = capsule["dependencies"][0]
        changed_request = copy.deepcopy(recorded["request"])
        changed_request["payload"]["messages"][0]["content"] = "changed"
        dependencies.invoke(recorded["kind"], recorded["operation"], changed_request)
        raise AssertionError("dependency mismatch should stop before an observation is produced")

    with pytest.raises(DependencyMismatchError, match="request mismatch"):
        completed_result = replay_exact(capsule, CallableFrameworkAdapter(runner))

    assert completed_result is None
    analysis.assert_not_called()


def test_replay_diff_core_remains_framework_neutral() -> None:
    core_paths = [
        REPOSITORY_ROOT / "src" / "traceforge" / "dependencies.py",
        REPOSITORY_ROOT / "src" / "traceforge" / "diff.py",
        REPOSITORY_ROOT / "src" / "traceforge" / "divergence.py",
        REPOSITORY_ROOT / "src" / "traceforge" / "regression.py",
        REPOSITORY_ROOT / "src" / "traceforge" / "replay.py",
    ]
    prohibited = (
        "langgraph",
        "langchain",
        "crewai",
        "autogen",
        "stategraph",
        "toolmessage",
        "aimessage",
        "supervisor",
        "planner",
    )

    for path in core_paths:
        source = path.read_text(encoding="utf-8").lower()
        for name in prohibited:
            assert name not in source


def test_place_a_never_receives_place_b_response() -> None:
    capsule, _ = _weather_artifacts()
    adapter = RecordedDependencyAdapter(capsule["dependencies"])
    kolkata_request = capsule["dependencies"][0]["request"]
    delhi_request = copy.deepcopy(kolkata_request)
    delhi_request["payload"]["messages"][0]["content"] = (
        "What is the weather in Delhi, and should I carry an umbrella?"
    )

    with pytest.raises(DependencyMismatchError, match="request mismatch"):
        adapter.invoke("model", "generate", delhi_request)

    assert adapter.consumed == 0
    outcome = adapter.invoke("model", "generate", kolkata_request)
    assert outcome["response"]["payload"]["tool_call"]["arguments"]["place"] == "Kolkata"


def test_missing_dependency_is_rejected(
    capsule_draft: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    capsule = seal_capsule(capsule_draft)
    analysis = _reject_completed_analysis(monkeypatch)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation, dependencies
        return copy.deepcopy(capsule["original_observation"])

    with pytest.raises(MissingDependencyError, match="sequence 1"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))
    analysis.assert_not_called()


def test_unexpected_extra_dependency_is_rejected(
    capsule_draft: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    capsule = seal_capsule(capsule_draft)
    analysis = _reject_completed_analysis(monkeypatch)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        recorded = capsule["dependencies"][0]
        dependencies.invoke(recorded["kind"], recorded["operation"], recorded["request"])
        dependencies.invoke(recorded["kind"], recorded["operation"], recorded["request"])
        return copy.deepcopy(capsule["original_observation"])

    with pytest.raises(UnexpectedDependencyError, match="no recorded fixture remains"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))
    analysis.assert_not_called()


def test_recorded_dependency_error_is_returned(capsule_draft: dict[str, Any]) -> None:
    dependency = capsule_draft["dependencies"][0]
    dependency["outcome"] = {
        "status": "errored",
        "error": {"type": "ControlledError", "message": "synthetic failure", "data": None},
    }
    capsule = seal_capsule(capsule_draft)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        outcome = dependencies.invoke(
            dependency["kind"], dependency["operation"], dependency["request"]
        )
        return {
            "execution_status": "errored",
            "events": [],
            "output": None,
            "error": outcome["error"],
        }

    result = replay_exact(capsule, CallableFrameworkAdapter(runner))
    assert result.replay_observation["error"]["type"] == "ControlledError"


def test_capsule_tampering_fails_before_runner(capsule_draft: dict[str, Any]) -> None:
    capsule = seal_capsule(capsule_draft)
    capsule["invocation"]["input"] = {"tampered": True}
    called = False

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        nonlocal called
        del invocation, dependencies
        called = True
        return {}

    with pytest.raises(IntegrityError, match="integrity.digest"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))
    assert called is False


def test_attempted_network_access_is_blocked(
    capsule_draft: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    capsule_draft["dependencies"] = []
    capsule = seal_capsule(capsule_draft)
    analysis = _reject_completed_analysis(monkeypatch)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation, dependencies
        socket.create_connection(("example.invalid", 443))
        return copy.deepcopy(capsule["original_observation"])

    with pytest.raises(LiveDependencyBlockedError, match="blocked"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))
    analysis.assert_not_called()


def test_runner_failure_produces_no_completed_analysis(
    capsule_draft: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    capsule_draft["dependencies"] = []
    capsule = seal_capsule(capsule_draft)
    analysis = _reject_completed_analysis(monkeypatch)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation, dependencies
        raise RuntimeError("controlled runner failure")

    with pytest.raises(RuntimeError, match="controlled runner failure"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))
    analysis.assert_not_called()


def test_original_observation_remains_unchanged() -> None:
    capsule, spec = _weather_artifacts()
    original_capsule = copy.deepcopy(capsule)

    result = replay_exact(capsule, CallableFrameworkAdapter(weather_runner), spec)

    assert capsule == original_capsule
    assert result.original_observation == original_capsule["original_observation"]
    assert result.replay_observation is not result.original_observation


def test_comparison_ignores_diagnostic_timing(capsule_draft: dict[str, Any]) -> None:
    capsule_draft["dependencies"] = []
    capsule_draft["original_observation"]["events"][0]["data"] = {
        "duration_ms": 10,
        "value": "same",
    }
    capsule = seal_capsule(capsule_draft)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation, dependencies
        observation = copy.deepcopy(capsule["original_observation"])
        observation["events"][0]["data"]["duration_ms"] = 999
        return observation

    result = replay_exact(capsule, CallableFrameworkAdapter(runner))
    assert result.deterministic_match is True


def test_behavioural_expectation_failure() -> None:
    capsule, spec = _weather_artifacts()
    failing = copy.deepcopy(spec)
    failing["assertions"][1]["expected"] = False

    result = replay_exact(capsule, CallableFrameworkAdapter(weather_runner), failing)

    assert result.regression is not None
    assert result.regression.passed is False


def test_regression_evaluator_rejects_missing_path() -> None:
    with pytest.raises(SemanticValidationError, match="does not exist"):
        evaluate_regression(
            {"output": {}},
            {
                "version": "0.1.0",
                "assertions": [{"path": "output.missing", "operator": "equals", "expected": 1}],
            },
        )
