from __future__ import annotations

import copy
import json
import socket
from pathlib import Path
from typing import Any

import pytest

from traceforge.dependencies import RecordedDependencyAdapter
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
from traceforge.replay import CallableFrameworkAdapter, replay_exact
from traceforge.sealing import seal_capsule
from traceforge.store import JsonFileCapsuleStore

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WEATHER_CAPSULE = REPOSITORY_ROOT / "examples" / "weather" / "replay-capsule.json"
WEATHER_SPEC = REPOSITORY_ROOT / "examples" / "weather" / "regression-spec.json"


def _weather_artifacts() -> tuple[dict[str, Any], dict[str, Any]]:
    store = JsonFileCapsuleStore()
    return store.load(WEATHER_CAPSULE), store.load(WEATHER_SPEC)


def test_successful_exact_replay_and_behavioural_pass() -> None:
    capsule, spec = _weather_artifacts()

    result = replay_exact(capsule, CallableFrameworkAdapter(weather_runner), spec)

    assert result.technical_status == "completed"
    assert result.deterministic_match is False
    assert result.replay_observation["output"]["umbrella_needed"] is True
    assert result.regression is not None and result.regression.passed


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


def test_missing_dependency_is_rejected(capsule_draft: dict[str, Any]) -> None:
    capsule = seal_capsule(capsule_draft)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation, dependencies
        return copy.deepcopy(capsule["original_observation"])

    with pytest.raises(MissingDependencyError, match="sequence 1"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))


def test_unexpected_extra_dependency_is_rejected(capsule_draft: dict[str, Any]) -> None:
    capsule = seal_capsule(capsule_draft)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        recorded = capsule["dependencies"][0]
        dependencies.invoke(recorded["kind"], recorded["operation"], recorded["request"])
        dependencies.invoke(recorded["kind"], recorded["operation"], recorded["request"])
        return copy.deepcopy(capsule["original_observation"])

    with pytest.raises(UnexpectedDependencyError, match="no recorded fixture remains"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))


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


def test_attempted_network_access_is_blocked(capsule_draft: dict[str, Any]) -> None:
    capsule_draft["dependencies"] = []
    capsule = seal_capsule(capsule_draft)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation, dependencies
        socket.create_connection(("example.invalid", 443))
        return copy.deepcopy(capsule["original_observation"])

    with pytest.raises(LiveDependencyBlockedError, match="blocked"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))


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
