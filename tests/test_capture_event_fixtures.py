from __future__ import annotations

import json
from pathlib import Path

import pytest

from traceforge.capture_events import sanitize_and_validate_event
from traceforge.exceptions import StructuralValidationError

FIXTURES = Path(__file__).resolve().parents[1] / "schemas/fixtures/capture-events"


def test_shared_positive_capture_event_fixture() -> None:
    sanitize_and_validate_event(json.loads((FIXTURES / "valid.json").read_text()))


def test_shared_positive_capture_event_03_fixture() -> None:
    sanitize_and_validate_event(
        json.loads((FIXTURES / "valid-v0.3-execution-span.json").read_text())
    )


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("invalid-*.json")))
def test_shared_negative_capture_event_fixtures(path: Path) -> None:
    with pytest.raises(StructuralValidationError):
        sanitize_and_validate_event(json.loads(path.read_text()))
