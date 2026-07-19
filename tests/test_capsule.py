from __future__ import annotations

from copy import deepcopy

import pytest

from traceforge import (
    IntegrityError,
    SealingError,
    SemanticValidationError,
    StructuralValidationError,
    seal_capsule,
    validate_capsule,
)
from traceforge.canonical import capsule_integrity_digest, request_fingerprint


def test_seal_and_validate_success_without_mutating_draft(capsule_draft: dict) -> None:
    original = deepcopy(capsule_draft)

    sealed = seal_capsule(capsule_draft)

    assert capsule_draft == original
    assert sealed["dependencies"][0]["request_fingerprint"] == request_fingerprint(
        sealed["dependencies"][0]["request"]
    )
    assert sealed["integrity"]["digest"] == capsule_integrity_digest(sealed)
    validate_capsule(sealed)


def test_seal_overwrites_untrusted_derived_fields(capsule_draft: dict) -> None:
    capsule_draft["dependencies"][0]["request_fingerprint"] = "untrusted"
    capsule_draft["integrity"] = {"algorithm": "untrusted", "digest": "untrusted"}

    sealed = seal_capsule(capsule_draft)

    assert sealed["dependencies"][0]["request_fingerprint"] != "untrusted"
    assert sealed["integrity"]["algorithm"] == "sha256"
    validate_capsule(sealed)


def test_seal_and_validate_http_dependency(capsule_draft: dict) -> None:
    capsule_draft["dependencies"] = [
        {
            "dependency_id": "dependency-http-1",
            "sequence": 1,
            "kind": "http",
            "operation": "GET",
            "request": {
                "method": "GET",
                "url": "https://invalid.example/synthetic",
                "headers": {"content-type": "application/json"},
                "body": None,
            },
            "outcome": {
                "status": "returned",
                "response": {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": {"synthetic": True},
                },
            },
            "duration_ms": 1,
        }
    ]

    validate_capsule(seal_capsule(capsule_draft))


def test_structural_validation_rejects_unknown_field(capsule_draft: dict) -> None:
    sealed = seal_capsule(capsule_draft)
    sealed["unexpected"] = True

    with pytest.raises(StructuralValidationError, match="unexpected"):
        validate_capsule(sealed)


def test_semantic_validation_rejects_duplicate_dependency_ids(capsule_draft: dict) -> None:
    duplicate = deepcopy(capsule_draft["dependencies"][0])
    duplicate["sequence"] = 2
    capsule_draft["dependencies"].append(duplicate)

    with pytest.raises(SealingError, match="dependency_id values must be unique"):
        seal_capsule(capsule_draft)


@pytest.mark.parametrize("sequences", [[2], [1, 1], [2, 1]])
def test_semantic_validation_rejects_noncontiguous_or_unordered_sequences(
    capsule_draft: dict, sequences: list[int]
) -> None:
    dependency = capsule_draft["dependencies"][0]
    capsule_draft["dependencies"] = []
    for index, sequence in enumerate(sequences):
        item = deepcopy(dependency)
        item["dependency_id"] = f"dependency-{index + 1}"
        item["sequence"] = sequence
        capsule_draft["dependencies"].append(item)

    with pytest.raises(SealingError, match="sequence values"):
        seal_capsule(capsule_draft)


def test_semantic_validation_rejects_unordered_event_sequences(capsule_draft: dict) -> None:
    event = capsule_draft["original_observation"]["events"][0]
    event["sequence"] = 2

    with pytest.raises(SealingError, match="original_observation.events sequence values"):
        seal_capsule(capsule_draft)


@pytest.mark.parametrize(
    ("status", "output", "error", "message"),
    [
        ("completed", {}, {"type": "E", "message": "", "data": None}, "completed"),
        ("errored", {}, {"type": "E", "message": "", "data": None}, "errored"),
        ("errored", None, None, "errored"),
        ("cancelled", {}, None, "cancelled"),
    ],
)
def test_semantic_validation_rejects_inconsistent_observation(
    capsule_draft: dict, status: str, output: object, error: object, message: str
) -> None:
    observation = capsule_draft["original_observation"]
    observation.update(execution_status=status, output=output, error=error)

    with pytest.raises(SealingError, match=message):
        seal_capsule(capsule_draft)


def test_validation_rejects_unsupported_version(capsule_draft: dict) -> None:
    capsule_draft["schema_version"] = "1.0.0"

    with pytest.raises(SealingError, match="unsupported schema_version"):
        seal_capsule(capsule_draft)


def test_sealing_rejects_non_finite_json_number(capsule_draft: dict) -> None:
    capsule_draft["invocation"]["input"] = float("nan")

    with pytest.raises(SealingError, match="cannot be canonicalized"):
        seal_capsule(capsule_draft)


def test_validation_rejects_tampered_request(capsule_draft: dict) -> None:
    sealed = seal_capsule(capsule_draft)
    sealed["dependencies"][0]["request"]["payload"] = {"changed": True}

    with pytest.raises(IntegrityError, match="request_fingerprint"):
        validate_capsule(sealed)


def test_validation_rejects_tampered_integrity_digest(capsule_draft: dict) -> None:
    sealed = seal_capsule(capsule_draft)
    sealed["integrity"]["digest"] = "sha256:" + "0" * 64

    with pytest.raises(IntegrityError, match="integrity.digest"):
        validate_capsule(sealed)


def test_validate_never_repairs_invalid_capsule(capsule_draft: dict) -> None:
    sealed = seal_capsule(capsule_draft)
    sealed["dependencies"][0]["request_fingerprint"] = "sha256:" + "0" * 64
    invalid = deepcopy(sealed)

    with pytest.raises(IntegrityError):
        validate_capsule(sealed)

    assert sealed == invalid


def test_public_exception_types_are_precise() -> None:
    assert not issubclass(StructuralValidationError, SemanticValidationError)
    assert not issubclass(IntegrityError, SemanticValidationError)
