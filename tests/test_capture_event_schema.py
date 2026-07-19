from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "schemas/capture-event-v0.schema.json").read_text()
)


def _event() -> dict:
    return {
        "schema_version": "0.2.0",
        "event_id": "event-1",
        "capture_id": "capture-1",
        "sequence": 1,
        "event_type": "capture_started",
        "occurred_at": "2026-07-19T12:00:00Z",
        "producer": {"name": "test", "version": "0.2.0"},
        "payload": {"arbitrary": [1, True, None]},
    }


def test_capture_event_schema_is_valid_and_accepts_sanitized_payload() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(_event())


@pytest.mark.parametrize("change", [("sequence", 0), ("event_type", "unknown")])
def test_capture_event_schema_rejects_invalid_envelope(change: tuple[str, object]) -> None:
    event = _event()
    event[change[0]] = change[1]
    with pytest.raises(ValidationError):
        Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(event)
