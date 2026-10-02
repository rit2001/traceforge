"""Semantic and integrity validation for sealed Replay Capsules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from traceforge.canonical import capsule_integrity_digest, request_fingerprint
from traceforge.exceptions import IntegrityError, SemanticValidationError
from traceforge.schema import validate_structure

SUPPORTED_SCHEMA_VERSIONS = frozenset({"0.1.0", "0.2.0"})


def _validate_supported_version(capsule: Mapping[str, Any]) -> None:
    version = capsule.get("schema_version")
    if version is not None and version not in SUPPORTED_SCHEMA_VERSIONS:
        raise SemanticValidationError(
            f"unsupported schema_version {version!r}; "
            f"expected one of {sorted(SUPPORTED_SCHEMA_VERSIONS)!r}"
        )


def _validate_ordered_sequences(items: Sequence[Mapping[str, Any]], path: str) -> None:
    sequences = [item["sequence"] for item in items]
    if len(sequences) != len(set(sequences)):
        raise SemanticValidationError(f"{path} sequence values must be unique")
    expected = list(range(1, len(sequences) + 1))
    if sequences != expected:
        raise SemanticValidationError(
            f"{path} sequence values must be ordered and contiguous from 1; "
            f"expected {expected}, got {sequences}"
        )


def validate_semantics(capsule: Mapping[str, Any]) -> None:
    """Validate v0 invariants that are deliberately outside JSON Schema."""
    _validate_supported_version(capsule)

    dependencies = capsule["dependencies"]
    dependency_ids = [dependency["dependency_id"] for dependency in dependencies]
    if len(dependency_ids) != len(set(dependency_ids)):
        raise SemanticValidationError("dependencies dependency_id values must be unique")
    _validate_ordered_sequences(dependencies, "dependencies")

    events = capsule["original_observation"]["events"]
    _validate_ordered_sequences(events, "original_observation.events")

    validate_observation_semantics(capsule["original_observation"])


def validate_observation_semantics(observation: Mapping[str, Any]) -> None:
    """Validate terminal status/output/error consistency for an observation."""
    status = observation["execution_status"]
    output = observation["output"]
    error = observation["error"]
    if status == "completed" and error is not None:
        raise SemanticValidationError("completed original_observation must have error set to null")
    if status == "errored" and (error is None or output is not None):
        raise SemanticValidationError(
            "errored original_observation must have a non-null error and output set to null"
        )
    if status == "cancelled" and output is not None:
        raise SemanticValidationError("cancelled original_observation must have output set to null")


def validate_integrity(capsule: Mapping[str, Any]) -> None:
    """Validate request fingerprints and the whole-capsule digest."""
    for index, dependency in enumerate(capsule["dependencies"]):
        expected = request_fingerprint(dependency["request"])
        actual = dependency["request_fingerprint"]
        if actual != expected:
            raise IntegrityError(
                f"dependencies.{index}.request_fingerprint does not match the sanitized request"
            )

    expected_digest = capsule_integrity_digest(capsule)
    actual_digest = capsule["integrity"]["digest"]
    if actual_digest != expected_digest:
        raise IntegrityError("integrity.digest does not match the capsule content")


def validate_capsule(capsule: Any) -> None:
    """Validate without modifying or repairing the supplied capsule."""
    if isinstance(capsule, Mapping):
        _validate_supported_version(capsule)
    validate_structure(capsule)
    validate_semantics(capsule)
    validate_integrity(capsule)
