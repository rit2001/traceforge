"""Versioned sanitized capture-event validation."""

from __future__ import annotations

import json
import sysconfig
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from traceforge.capture import BestEffortRedactionScanner
from traceforge.exceptions import StructuralValidationError


def _path() -> Path:
    source = Path(__file__).resolve().parents[2] / "schemas/capture-event-v0.schema.json"
    if source.is_file():
        return source
    return (
        Path(sysconfig.get_path("data")) / "share/traceforge/schemas/capture-event-v0.schema.json"
    )


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(_path().read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def sanitize_and_validate_event(event: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitized copy that conforms to the capture-event envelope."""
    sanitized = deepcopy(event)
    if "payload" in sanitized:
        sanitized["payload"] = (
            BestEffortRedactionScanner().scan(sanitized["payload"], "$.payload").value
        )
    errors = sorted(_validator().iter_errors(sanitized), key=lambda item: list(item.path))
    if errors:
        error = errors[0]
        location = ".".join(map(str, error.path)) or "<root>"
        raise StructuralValidationError(f"capture event {location}: {error.message}")
    return sanitized
