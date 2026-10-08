"""Semantic and integrity validation for sealed Replay Capsules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from traceforge.canonical import capsule_integrity_digest, request_fingerprint
from traceforge.exceptions import IntegrityError, SemanticValidationError
from traceforge.schema import validate_structure

SUPPORTED_SCHEMA_VERSIONS = frozenset({"0.1.0", "0.2.0", "0.3.0"})


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

    if capsule["schema_version"] == "0.3.0":
        _validate_execution_spans(capsule)

    validate_observation_semantics(capsule["original_observation"])


def _validate_execution_spans(capsule: Mapping[str, Any]) -> None:
    spans = capsule["execution_spans"]
    _validate_ordered_sequences(spans, "execution_spans")
    execution_span_ids = [span["execution_span_id"] for span in spans]
    if len(execution_span_ids) != len(set(execution_span_ids)):
        raise SemanticValidationError("execution_spans execution_span_id values must be unique")

    known: set[str] = set()
    for index, execution_span in enumerate(spans):
        for label in ("kind", "name", "component"):
            value = execution_span[label]
            if not value.strip() or any(
                ord(character) < 32 or ord(character) == 127 for character in value
            ):
                raise SemanticValidationError(
                    f"execution_spans.{index}.{label} must be non-blank and control-free"
                )
        execution_span_id = execution_span["execution_span_id"]
        parent_execution_span_id = execution_span["parent_execution_span_id"]
        if index == 0:
            if parent_execution_span_id is not None:
                raise SemanticValidationError(
                    "execution_spans must start with exactly one root whose "
                    "parent_execution_span_id is null"
                )
        elif parent_execution_span_id is None:
            raise SemanticValidationError(
                "execution_spans must contain exactly one root; later "
                "parent_execution_span_id values cannot be null"
            )
        elif parent_execution_span_id == execution_span_id:
            raise SemanticValidationError("execution_spans cannot contain a self-parent")
        elif parent_execution_span_id not in known:
            raise SemanticValidationError(
                f"execution_spans.{index}.parent_execution_span_id must reference an earlier span"
            )
        known.add(execution_span_id)

    for domain, records in (
        ("dependencies", capsule["dependencies"]),
        ("original_observation.events", capsule["original_observation"]["events"]),
    ):
        for index, record in enumerate(records):
            if record["execution_span_id"] not in known:
                raise SemanticValidationError(
                    f"{domain}.{index}.execution_span_id must reference an execution span"
                )


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
