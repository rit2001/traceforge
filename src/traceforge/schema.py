"""Replay Capsule v0 JSON Schema loading and structural validation."""

from __future__ import annotations

import json
import sysconfig
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from traceforge.exceptions import StructuralValidationError


def _schema_path() -> Path:
    repository_schema = (
        Path(__file__).resolve().parents[2] / "schemas" / "replay-capsule-v0.schema.json"
    )
    if repository_schema.is_file():
        return repository_schema
    return (
        Path(sysconfig.get_path("data"))
        / "share"
        / "traceforge"
        / "schemas"
        / "replay-capsule-v0.schema.json"
    )


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    path = _schema_path()
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        raise StructuralValidationError(f"cannot load Replay Capsule schema at {path}: {exc}") from exc
    return schema


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema(), format_checker=FormatChecker())


def _path(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.absolute_path) or "<root>"


def validate_structure(capsule: Any) -> None:
    """Raise a precise error if ``capsule`` fails structural validation."""
    errors = sorted(
        _validator().iter_errors(capsule),
        key=lambda error: ([str(part) for part in error.absolute_path], error.message),
    )
    if errors:
        first = errors[0]
        raise StructuralValidationError(f"{_path(first)}: {first.message}")


def validate_observation_structure(observation: Any) -> None:
    """Validate a newly produced observation against the accepted v0 definition."""
    validator = Draft202012Validator(
        {"$ref": "#/$defs/originalObservation", "$defs": _schema()["$defs"]},
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(observation),
        key=lambda error: ([str(part) for part in error.absolute_path], error.message),
    )
    if errors:
        first = errors[0]
        raise StructuralValidationError(f"replay_observation.{_path(first)}: {first.message}")
