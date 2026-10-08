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

CAPTURE_EVENT_SCHEMA_FILENAMES = {
    "0.2.0": "capture-event-v0.schema.json",
    "0.3.0": "capture-event-v0.3.schema.json",
}


def _path(version: str) -> Path:
    filename = CAPTURE_EVENT_SCHEMA_FILENAMES[version]
    source = Path(__file__).resolve().parents[2] / "schemas" / filename
    if source.is_file():
        return source
    return Path(sysconfig.get_path("data")) / "share/traceforge/schemas" / filename


@lru_cache(maxsize=len(CAPTURE_EVENT_SCHEMA_FILENAMES))
def _validator(version: str) -> Draft202012Validator:
    schema = json.loads(_path(version).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def sanitize_and_validate_event(event: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitized copy that conforms to the capture-event envelope."""
    sanitized = deepcopy(event)
    version = sanitized.get("schema_version")
    if version not in CAPTURE_EVENT_SCHEMA_FILENAMES:
        raise StructuralValidationError(
            f"capture event schema_version: unsupported capture-event version {version!r}"
        )
    if "payload" in sanitized:
        scanned = BestEffortRedactionScanner().scan(sanitized["payload"], "$.payload")
        if sanitized.get("event_type") == "execution_span_recorded" and scanned.actions:
            raise StructuralValidationError(
                "capture event execution span labels must already be safe stable values"
            )
        sanitized["payload"] = scanned.value
    errors = sorted(_validator(version).iter_errors(sanitized), key=lambda item: list(item.path))
    if errors:
        error = errors[0]
        location = ".".join(map(str, error.path)) or "<root>"
        raise StructuralValidationError(f"capture event {location}: {error.message}")
    return sanitized
