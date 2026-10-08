"""Explicit promotion from a caller-supplied replay result into a regression spec."""

from __future__ import annotations

import json
from copy import deepcopy
from math import isfinite
from typing import Any

from traceforge.exceptions import SemanticValidationError
from traceforge.regression import evaluate_regression
from traceforge.replay import ReplayResult


def _copy_strict_json(value: Any, location: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise SemanticValidationError(f"{location} must contain only finite JSON numbers")
        return value
    if isinstance(value, list):
        return [_copy_strict_json(item, f"{location}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, dict):
        copied: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SemanticValidationError(f"{location} JSON object keys must be strings")
            copied[key] = _copy_strict_json(item, f"{location}.{key}")
        return copied
    raise SemanticValidationError(
        f"{location} must contain only JSON null, booleans, numbers, strings, arrays, or objects"
    )


def promote_regression(
    replay_result: ReplayResult,
    assertions: Any,
    *,
    developer_approved: bool,
) -> dict[str, Any]:
    """Create a detached ``RegressionSpec 0.1.0`` from explicit selections.

    The public function trusts the caller-supplied ``ReplayResult``; the type
    does not prove that ``replay_exact()`` produced it. Promotion records caller
    intent and does not change evidence or runtime-derived values.
    """
    if developer_approved is not True:
        raise SemanticValidationError("promotion requires explicit developer approval")
    if not isinstance(replay_result, ReplayResult):
        raise SemanticValidationError("promotion requires a ReplayResult")
    if replay_result.technical_status != "completed":
        raise SemanticValidationError("promotion requires a technically completed replay")
    if replay_result.execution_diff is None or replay_result.divergence_analysis is None:
        raise SemanticValidationError(
            "promotion requires supplied execution diff and divergence analysis values"
        )

    copied_assertions = _copy_strict_json(assertions, "promotion assertions")
    if isinstance(copied_assertions, list):
        canonical_assertions = [
            json.dumps(
                _copy_strict_json(assertion, f"promotion assertion {index}"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for index, assertion in enumerate(copied_assertions)
        ]
        if len(set(canonical_assertions)) != len(canonical_assertions):
            raise SemanticValidationError("promotion assertions must not contain exact duplicates")
    specification = {"version": "0.1.0", "assertions": copied_assertions}
    evaluation = evaluate_regression(replay_result.replay_observation, specification)
    if not evaluation.passed:
        raise SemanticValidationError(
            "promoted expectations must pass against the supplied replay observation"
        )
    return deepcopy(specification)
