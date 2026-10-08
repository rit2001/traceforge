from __future__ import annotations

import copy
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from traceforge import promote_regression
from traceforge.examples.weather_agent import run as weather_runner
from traceforge.exceptions import SemanticValidationError
from traceforge.regression import evaluate_regression
from traceforge.replay import CallableFrameworkAdapter, ReplayResult, replay_exact

ROOT = Path(__file__).resolve().parents[1]
CAPSULE = ROOT / "examples/weather/replay-capsule.json"


def _repaired_replay() -> tuple[dict, ReplayResult]:
    capsule = json.loads(CAPSULE.read_text(encoding="utf-8"))
    result = replay_exact(capsule, CallableFrameworkAdapter(weather_runner))
    return capsule, result


def _umbrella_assertions() -> list[dict]:
    return [{"path": "output.umbrella_needed", "operator": "equals", "expected": True}]


def test_repaired_non_matching_replay_can_be_promoted() -> None:
    _, result = _repaired_replay()

    promoted = promote_regression(
        result,
        _umbrella_assertions(),
        developer_approved=True,
    )

    assert result.technical_status == "completed"
    assert result.deterministic_match is False
    assert result.regression is None
    assert result.execution_diff is not None
    assert result.execution_diff.to_dict()["matches"] is False
    assert promoted == {"version": "0.1.0", "assertions": _umbrella_assertions()}
    assert evaluate_regression(result.replay_observation, promoted).passed is True


def test_failed_old_regression_does_not_block_explicit_new_promotion() -> None:
    capsule = json.loads(CAPSULE.read_text(encoding="utf-8"))
    old_spec = {
        "version": "0.1.0",
        "assertions": [{"path": "output.umbrella_needed", "operator": "equals", "expected": False}],
    }
    result = replay_exact(capsule, CallableFrameworkAdapter(weather_runner), old_spec)

    promoted = promote_regression(
        result,
        _umbrella_assertions(),
        developer_approved=True,
    )

    assert result.regression is not None and result.regression.passed is False
    assert promoted == {"version": "0.1.0", "assertions": _umbrella_assertions()}


def test_promotion_requires_explicit_developer_approval() -> None:
    _, result = _repaired_replay()

    with pytest.raises(TypeError, match="developer_approved"):
        promote_regression(result, _umbrella_assertions())
    with pytest.raises(SemanticValidationError, match="explicit developer approval"):
        promote_regression(result, _umbrella_assertions(), developer_approved=False)
    with pytest.raises(SemanticValidationError, match="explicit developer approval"):
        promote_regression(result, _umbrella_assertions(), developer_approved=1)


def test_technical_replay_failure_cannot_be_promoted() -> None:
    failed = ReplayResult(
        technical_status="errored",
        original_observation={},
        replay_observation={},
        deterministic_match=False,
        regression=None,
    )

    with pytest.raises(SemanticValidationError, match="technically completed"):
        promote_regression(failed, _umbrella_assertions(), developer_approved=True)


def test_public_api_trusts_caller_supplied_result_without_attesting_provenance() -> None:
    _, actual = _repaired_replay()
    fabricated = ReplayResult(
        technical_status="completed",
        original_observation=copy.deepcopy(actual.original_observation),
        replay_observation=copy.deepcopy(actual.replay_observation),
        deterministic_match=False,
        regression=None,
        execution_diff=actual.execution_diff,
        divergence_analysis=actual.divergence_analysis,
    )

    promoted = promote_regression(
        fabricated,
        _umbrella_assertions(),
        developer_approved=True,
    )

    assert promoted["assertions"] == _umbrella_assertions()
    assert "trusts the caller-supplied" in (promote_regression.__doc__ or "")


def test_promotion_does_not_mutate_evidence_or_derived_results() -> None:
    capsule, result = _repaired_replay()
    capsule_before = copy.deepcopy(capsule)
    replay_before = copy.deepcopy(result)
    assertions = _umbrella_assertions()

    promoted = promote_regression(result, assertions, developer_approved=True)
    promoted["assertions"][0]["expected"] = False
    assertions[0]["expected"] = "changed later"

    assert capsule == capsule_before
    assert result == replay_before
    assert result.execution_diff == replay_before.execution_diff
    assert result.divergence_analysis == replay_before.divergence_analysis


def test_promotion_includes_only_selected_existing_regression_assertions() -> None:
    _, result = _repaired_replay()
    selection = [
        {
            "path": "output.answer",
            "operator": "contains",
            "expected": "Take an umbrella",
        }
    ]

    promoted = promote_regression(result, selection, developer_approved=True)

    assert promoted == {"version": "0.1.0", "assertions": selection}
    serialized = json.dumps(promoted, sort_keys=True)
    assert "temperature_c" not in serialized
    assert "execution_diff" not in serialized
    assert "divergence_analysis" not in serialized
    assert "deterministic_match" not in serialized


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        7,
        2.5,
        ["quoted\nvalue", False, None, 4],
        {"deep": {"array": [1, "two", {"slash": "\\"}]}},
        "quotes: ' \"; source-like: __import__('os')\nnext line\\tail",
    ],
)
def test_promotion_preserves_supported_json_expectation_values(value: Any) -> None:
    _, result = _repaired_replay()
    observation = copy.deepcopy(result.replay_observation)
    observation["output"]["selected"] = copy.deepcopy(value)
    supplied = replace(result, replay_observation=observation)

    promoted = promote_regression(
        supplied,
        [{"path": "output.selected", "operator": "equals", "expected": value}],
        developer_approved=True,
    )

    assert promoted["assertions"][0]["expected"] == value
    assert json.loads(json.dumps(promoted, allow_nan=False)) == promoted


@pytest.mark.parametrize(
    "unsupported",
    [
        object(),
        ("tuple",),
        {"set"},
        b"bytes",
        math.nan,
        math.inf,
        -math.inf,
        {1: "non-string key"},
    ],
)
def test_promotion_rejects_values_that_are_not_strict_json(unsupported: Any) -> None:
    _, result = _repaired_replay()
    observation = copy.deepcopy(result.replay_observation)
    observation["output"]["selected"] = unsupported
    supplied = replace(result, replay_observation=observation)

    with pytest.raises(SemanticValidationError, match="JSON"):
        promote_regression(
            supplied,
            [{"path": "output.selected", "operator": "equals", "expected": unsupported}],
            developer_approved=True,
        )


def test_promotion_accepts_deep_json_and_rejects_exact_duplicate_assertions() -> None:
    _, result = _repaired_replay()
    deep: Any = "leaf"
    for _ in range(40):
        deep = {"nested": [deep]}
    observation = copy.deepcopy(result.replay_observation)
    observation["output"]["selected"] = copy.deepcopy(deep)
    supplied = replace(result, replay_observation=observation)
    assertion = {"path": "output.selected", "operator": "equals", "expected": deep}

    promoted = promote_regression(supplied, [assertion], developer_approved=True)

    assert promoted["assertions"][0]["expected"] == deep
    with pytest.raises(SemanticValidationError, match="duplicate"):
        promote_regression(supplied, [assertion, copy.deepcopy(assertion)], developer_approved=True)


def test_promoted_spec_has_no_hidden_aliases_to_inputs_or_supplied_result() -> None:
    _, result = _repaired_replay()
    selected = {"nested": ["stable"]}
    observation = copy.deepcopy(result.replay_observation)
    observation["output"]["selected"] = selected
    supplied = replace(result, replay_observation=observation)
    assertions = [{"path": "output.selected", "operator": "equals", "expected": selected}]

    promoted = promote_regression(supplied, assertions, developer_approved=True)
    assertions[0]["expected"]["nested"].append("caller mutation")
    supplied.replay_observation["output"]["selected"]["nested"].append("result mutation")
    assert supplied.execution_diff is not None
    assert supplied.divergence_analysis is not None
    supplied.execution_diff.to_dict()["differences"].append({"forged": True})
    supplied.divergence_analysis.to_dict()["findings"].append("forged")

    assert promoted["assertions"][0]["expected"] == {"nested": ["stable"]}


def test_promotion_reuses_regression_spec_validation_and_requires_current_pass() -> None:
    _, result = _repaired_replay()

    with pytest.raises(SemanticValidationError, match="unsupported operator"):
        promote_regression(
            result,
            [{"path": "output.answer", "operator": "matches", "expected": ".*"}],
            developer_approved=True,
        )
    with pytest.raises(SemanticValidationError, match="must pass"):
        promote_regression(
            result,
            [{"path": "output.umbrella_needed", "operator": "equals", "expected": False}],
            developer_approved=True,
        )


@pytest.mark.parametrize(
    ("assertions", "message"),
    [
        ([], "non-empty array"),
        ([{"operator": "equals", "expected": True}], "exactly path, operator, and expected"),
        (
            [{"path": "output.missing", "operator": "equals", "expected": True}],
            "does not exist",
        ),
    ],
)
def test_promotion_rejects_empty_missing_and_nonexistent_assertions(
    assertions: list[dict[str, Any]], message: str
) -> None:
    _, result = _repaired_replay()

    with pytest.raises(SemanticValidationError, match=message):
        promote_regression(result, assertions, developer_approved=True)


def test_promotion_is_framework_neutral() -> None:
    source = (ROOT / "src/traceforge/promotion.py").read_text(encoding="utf-8").lower()

    assert "langgraph" not in source
    assert "stategraph" not in source
