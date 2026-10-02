"""Exact replay orchestration for trusted local subject runners."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from traceforge.dependencies import RecordedDependencyAdapter, assert_replayable_tool_failures
from traceforge.exceptions import SemanticValidationError
from traceforge.interfaces import DependencyAdapter, FrameworkAdapter
from traceforge.metrics import replay as record_replay
from traceforge.network import block_network
from traceforge.observability import replay_span
from traceforge.regression import RegressionResult, evaluate_regression
from traceforge.schema import validate_observation_structure
from traceforge.validation import validate_capsule, validate_observation_semantics

Runner = Callable[[Any, DependencyAdapter], dict[str, Any]]
_DIAGNOSTIC_KEYS = {"duration_ms", "recorded_at", "timestamp", "started_at", "finished_at"}


@dataclass(frozen=True)
class ReplayResult:
    technical_status: str
    original_observation: dict[str, Any]
    replay_observation: dict[str, Any]
    deterministic_match: bool
    regression: RegressionResult | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "technical_status": self.technical_status,
            "original_observation": self.original_observation,
            "replay_observation": self.replay_observation,
            "comparison": {
                "deterministic_match": self.deterministic_match,
                "ignored_fields": sorted(_DIAGNOSTIC_KEYS),
            },
            "regression": None if self.regression is None else self.regression.to_dict(),
        }


@dataclass(frozen=True)
class CallableFrameworkAdapter:
    runner: Runner

    def run(self, invocation_input: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        return self.runner(invocation_input, dependencies)


def load_runner(reference: str) -> CallableFrameworkAdapter:
    """Load trusted local ``MODULE:FUNCTION`` code for CLI replay."""
    module_name, separator, function_name = reference.partition(":")
    if not separator or not module_name or not function_name:
        raise SemanticValidationError("runner must use MODULE:FUNCTION syntax")
    try:
        runner = getattr(import_module(module_name), function_name)
    except (ImportError, AttributeError) as exc:
        raise SemanticValidationError(
            f"cannot load trusted local runner {reference!r}: {exc}"
        ) from exc
    if not callable(runner):
        raise SemanticValidationError(f"trusted local runner {reference!r} is not callable")
    return CallableFrameworkAdapter(runner)


def _without_diagnostics(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_diagnostics(item)
            for key, item in value.items()
            if key not in _DIAGNOSTIC_KEYS
        }
    if isinstance(value, list):
        return [_without_diagnostics(item) for item in value]
    return value


def replay_exact(
    capsule: dict[str, Any],
    framework: FrameworkAdapter,
    regression_spec: Any | None = None,
    correlation: dict[str, str] | None = None,
) -> ReplayResult:
    """Replay a valid capsule with recorded fixtures and zero live networking."""
    try:
        with replay_span(correlation):
            result = _replay_exact(capsule, framework, regression_spec)
    except Exception:
        record_replay(False)
        raise
    record_replay(True)
    return result


def _replay_exact(
    capsule: dict[str, Any], framework: FrameworkAdapter, regression_spec: Any | None
) -> ReplayResult:
    validate_capsule(capsule)
    original_observation = deepcopy(capsule["original_observation"])
    assert_replayable_tool_failures(capsule["dependencies"])
    dependencies = RecordedDependencyAdapter(capsule["dependencies"])

    with block_network():
        replay_observation = framework.run(deepcopy(capsule["invocation"]["input"]), dependencies)
    dependencies.assert_consumed()
    validate_observation_structure(replay_observation)
    validate_observation_semantics(replay_observation)

    regression = (
        None
        if regression_spec is None
        else evaluate_regression(replay_observation, regression_spec)
    )
    result = ReplayResult(
        technical_status="completed",
        original_observation=original_observation,
        replay_observation=deepcopy(replay_observation),
        deterministic_match=(
            _without_diagnostics(original_observation) == _without_diagnostics(replay_observation)
        ),
        regression=regression,
    )
    return result
