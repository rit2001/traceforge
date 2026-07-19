"""Developer-authored regression specifications and deterministic evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from traceforge.exceptions import SemanticValidationError


@dataclass(frozen=True)
class AssertionResult:
    path: str
    operator: str
    expected: Any
    actual: Any
    passed: bool


@dataclass(frozen=True)
class RegressionResult:
    passed: bool
    assertions: tuple[AssertionResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "assertions": [asdict(item) for item in self.assertions]}


def _resolve_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise SemanticValidationError(f"regression path {path!r} does not exist")
        current = current[part]
    return current


def evaluate_regression(observation: dict[str, Any], spec: Any) -> RegressionResult:
    """Evaluate the small deterministic assertion set used by the MVP."""
    if not isinstance(spec, dict) or spec.get("version") != "0.1.0":
        raise SemanticValidationError("regression specification version must be '0.1.0'")
    assertions = spec.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        raise SemanticValidationError("regression specification assertions must be a non-empty array")

    results: list[AssertionResult] = []
    for index, assertion in enumerate(assertions):
        if not isinstance(assertion, dict):
            raise SemanticValidationError(f"regression assertion {index} must be an object")
        allowed = {"path", "operator", "expected"}
        if set(assertion) != allowed:
            raise SemanticValidationError(
                f"regression assertion {index} must contain exactly path, operator, and expected"
            )
        path = assertion["path"]
        operator = assertion["operator"]
        if not isinstance(path, str) or not path:
            raise SemanticValidationError(f"regression assertion {index} path must be non-empty")
        actual = _resolve_path(observation, path)
        expected = assertion["expected"]
        if operator == "equals":
            passed = actual == expected
        elif operator == "contains":
            passed = isinstance(actual, (str, list)) and expected in actual
        else:
            raise SemanticValidationError(
                f"regression assertion {index} has unsupported operator {operator!r}"
            )
        results.append(AssertionResult(path, operator, expected, actual, passed))

    frozen = tuple(results)
    return RegressionResult(all(result.passed for result in frozen), frozen)
