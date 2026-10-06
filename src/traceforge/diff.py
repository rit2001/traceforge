"""Portable structured comparison of captured and replayed executions."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from traceforge.canonical import canonicalize
from traceforge.exceptions import IntegrityError, SemanticValidationError

_DIAGNOSTIC_KEYS = frozenset(
    {"duration_ms", "recorded_at", "timestamp", "started_at", "finished_at"}
)
_MISSING = object()

Difference = dict[str, Any]
Record = dict[str, Any]
Projection = Callable[[Record], Record]
Anchor = Callable[[Record], tuple[str, str]]
RecordComparator = Callable[[Record, Record, int, int, list[Difference]], None]
_DOMAIN_RECORD_NAMES = {"dependencies": "dependency", "events": "event"}


@dataclass(frozen=True)
class ExecutionDiff:
    """Alias-isolated structured execution comparison result."""

    _canonical_document: bytes = field(repr=False)
    _canonical_analysis_metadata: bytes | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Return a newly allocated JSON-compatible representation."""
        document = json.loads(self._canonical_document)
        if not isinstance(document, dict):  # pragma: no cover - construction invariant
            raise IntegrityError("ExecutionDiff must contain a JSON object")
        return document

    def _analysis_summary(self) -> dict[str, Any]:
        """Return compact metadata retained by the trusted comparator."""
        if self._canonical_analysis_metadata is None:
            raise IntegrityError("ExecutionDiff has no trusted analysis metadata")
        try:
            document = json.loads(self._canonical_analysis_metadata)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise IntegrityError("ExecutionDiff analysis metadata is not valid JSON") from exc
        if not isinstance(document, dict):  # pragma: no cover - construction invariant
            raise IntegrityError("ExecutionDiff analysis metadata must contain a JSON object")
        if canonicalize(document) != self._canonical_analysis_metadata:
            raise IntegrityError("ExecutionDiff analysis metadata must use canonical JSON")
        return document


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise IntegrityError(
        f"value cannot be canonicalized with RFC 8785: unsupported type {type(value)}"
    )


def _snapshot(value: Any = _MISSING) -> dict[str, Any]:
    if value is _MISSING:
        return {"present": False, "type": "missing", "value": None}
    return {"present": True, "type": _json_type(value), "value": deepcopy(value)}


def _difference(
    section: str,
    code: str,
    expected_path: str | None,
    actual_path: str | None,
    expected: Any = _MISSING,
    actual: Any = _MISSING,
) -> Difference:
    return {
        "section": section,
        "code": code,
        "path": expected_path if expected_path is not None else actual_path,
        "expected_path": expected_path,
        "actual_path": actual_path,
        "expected": _snapshot(expected),
        "actual": _snapshot(actual),
    }


def _pointer(path: str, segment: str | int) -> str:
    encoded = str(segment).replace("~", "~0").replace("/", "~1")
    return f"{path}/{encoded}"


def _jcs_order(keys: set[str]) -> list[str]:
    return sorted(keys, key=lambda key: key.encode("utf-16be"))


def _strip_diagnostics(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_diagnostics(item)
            for key, item in value.items()
            if key not in _DIAGNOSTIC_KEYS
        }
    if isinstance(value, list):
        return [_strip_diagnostics(item) for item in value]
    return deepcopy(value)


def _compare_json(
    expected: Any,
    actual: Any,
    *,
    expected_path: str,
    actual_path: str,
    section: str,
    differences: list[Difference],
) -> None:
    expected_type = _json_type(expected)
    actual_type = _json_type(actual)
    if expected_type != actual_type:
        differences.append(
            _difference(
                section,
                "type_changed",
                expected_path,
                actual_path,
                expected,
                actual,
            )
        )
        return

    if expected_type == "object":
        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in _jcs_order(expected_keys | actual_keys):
            child_expected_path = _pointer(expected_path, key)
            child_actual_path = _pointer(actual_path, key)
            if key not in actual:
                differences.append(
                    _difference(
                        section,
                        "object_key_missing",
                        child_expected_path,
                        None,
                        expected[key],
                    )
                )
            elif key not in expected:
                differences.append(
                    _difference(
                        section,
                        "object_key_extra",
                        None,
                        child_actual_path,
                        actual=actual[key],
                    )
                )
            else:
                _compare_json(
                    expected[key],
                    actual[key],
                    expected_path=child_expected_path,
                    actual_path=child_actual_path,
                    section=section,
                    differences=differences,
                )
        return

    if expected_type == "array":
        if len(expected) != len(actual):
            differences.append(
                _difference(
                    section,
                    "array_length_changed",
                    expected_path,
                    actual_path,
                    expected,
                    actual,
                )
            )
        for index in range(min(len(expected), len(actual))):
            _compare_json(
                expected[index],
                actual[index],
                expected_path=_pointer(expected_path, index),
                actual_path=_pointer(actual_path, index),
                section=section,
                differences=differences,
            )
        for index in range(len(actual), len(expected)):
            differences.append(
                _difference(
                    section,
                    "array_item_missing",
                    _pointer(expected_path, index),
                    None,
                    expected[index],
                )
            )
        for index in range(len(expected), len(actual)):
            differences.append(
                _difference(
                    section,
                    "array_item_extra",
                    None,
                    _pointer(actual_path, index),
                    actual=actual[index],
                )
            )
        return

    if canonicalize(expected) != canonicalize(actual):
        differences.append(
            _difference(
                section,
                "value_changed",
                expected_path,
                actual_path,
                expected,
                actual,
            )
        )


def _validate_sequence(records: list[Record], label: str) -> None:
    for index, record in enumerate(records, start=1):
        if record.get("sequence") != index:
            raise SemanticValidationError(
                f"{label} sequence values must be one-based, contiguous, "
                "and agree with array position"
            )


def _event_projection(record: Record) -> Record:
    return {
        "kind": record["kind"],
        "name": record["name"],
        "data": _strip_diagnostics(record["data"]),
    }


def _dependency_projection(record: Record) -> Record:
    return {
        "kind": record["kind"],
        "operation": record["operation"],
        "request": deepcopy(record["request"]),
        "outcome": deepcopy(record["outcome"]),
    }


def _lcs_pairs(expected: list[bytes], actual: list[bytes]) -> list[tuple[int, int]]:
    rows = len(expected)
    columns = len(actual)
    lengths = [[0] * (columns + 1) for _ in range(rows + 1)]
    for expected_index in range(rows - 1, -1, -1):
        for actual_index in range(columns - 1, -1, -1):
            if expected[expected_index] == actual[actual_index]:
                lengths[expected_index][actual_index] = (
                    1 + lengths[expected_index + 1][actual_index + 1]
                )
            else:
                lengths[expected_index][actual_index] = max(
                    lengths[expected_index + 1][actual_index],
                    lengths[expected_index][actual_index + 1],
                )

    pairs: list[tuple[int, int]] = []
    expected_index = 0
    actual_index = 0
    while expected_index < rows and actual_index < columns:
        if expected[expected_index] == actual[actual_index]:
            pairs.append((expected_index, actual_index))
            expected_index += 1
            actual_index += 1
        elif lengths[expected_index + 1][actual_index] >= lengths[expected_index][actual_index + 1]:
            expected_index += 1
        else:
            actual_index += 1
    return pairs


def _missing_record(domain: str, record: Record, index: int) -> Difference:
    path = _pointer(f"/{domain}", index)
    return _difference(domain, f"{_DOMAIN_RECORD_NAMES[domain]}_missing", path, None, record)


def _extra_record(domain: str, record: Record, index: int) -> Difference:
    path = _pointer(f"/{domain}", index)
    return _difference(domain, f"{_DOMAIN_RECORD_NAMES[domain]}_extra", None, path, actual=record)


def _compare_gap(
    expected: list[Record],
    actual: list[Record],
    *,
    expected_start: int,
    expected_end: int,
    actual_start: int,
    actual_end: int,
    domain: str,
    anchor: Anchor,
    compare_record: RecordComparator,
    differences: list[Difference],
) -> None:
    expected_indices = list(range(expected_start, expected_end))
    actual_indices = list(range(actual_start, actual_end))
    if not expected_indices:
        differences.extend(_extra_record(domain, actual[index], index) for index in actual_indices)
        return
    if not actual_indices:
        differences.extend(
            _missing_record(domain, expected[index], index) for index in expected_indices
        )
        return
    if len(expected_indices) == len(actual_indices) == 1:
        compare_record(
            expected[expected_indices[0]],
            actual[actual_indices[0]],
            expected_indices[0],
            actual_indices[0],
            differences,
        )
        return

    expected_anchors = Counter(anchor(expected[index]) for index in expected_indices)
    actual_anchors = Counter(anchor(actual[index]) for index in actual_indices)
    actual_by_anchor = {anchor(actual[index]): index for index in actual_indices}
    pairs: list[tuple[int, int]] = []
    for expected_index in expected_indices:
        candidate = anchor(expected[expected_index])
        if expected_anchors[candidate] == 1 and actual_anchors[candidate] == 1:
            pairs.append((expected_index, actual_by_anchor[candidate]))

    pairs.sort()
    paired_expected = {expected_index for expected_index, _ in pairs}
    paired_actual = {actual_index for _, actual_index in pairs}
    for expected_index, actual_index in pairs:
        compare_record(
            expected[expected_index],
            actual[actual_index],
            expected_index,
            actual_index,
            differences,
        )
    differences.extend(
        _missing_record(domain, expected[index], index)
        for index in expected_indices
        if index not in paired_expected
    )
    differences.extend(
        _extra_record(domain, actual[index], index)
        for index in actual_indices
        if index not in paired_actual
    )


def _compare_ordered_records(
    expected: list[Record],
    actual: list[Record],
    *,
    domain: str,
    projection: Projection,
    anchor: Anchor,
    compare_record: RecordComparator,
) -> list[Difference]:
    expected_signatures = [canonicalize(projection(record)) for record in expected]
    actual_signatures = [canonicalize(projection(record)) for record in actual]
    if expected_signatures == actual_signatures:
        return []
    if Counter(expected_signatures) == Counter(actual_signatures):
        path = f"/{domain}"
        return [
            _difference(
                domain,
                f"{_DOMAIN_RECORD_NAMES[domain]}_reordered",
                path,
                path,
                [projection(record) for record in expected],
                [projection(record) for record in actual],
            )
        ]

    differences: list[Difference] = []
    pairs = _lcs_pairs(expected_signatures, actual_signatures)
    expected_start = 0
    actual_start = 0
    for expected_index, actual_index in [*pairs, (len(expected), len(actual))]:
        _compare_gap(
            expected,
            actual,
            expected_start=expected_start,
            expected_end=expected_index,
            actual_start=actual_start,
            actual_end=actual_index,
            domain=domain,
            anchor=anchor,
            compare_record=compare_record,
            differences=differences,
        )
        expected_start = expected_index + 1
        actual_start = actual_index + 1
    return differences


def _compare_event_record(
    expected: Record,
    actual: Record,
    expected_index: int,
    actual_index: int,
    differences: list[Difference],
) -> None:
    expected_base = _pointer("/events", expected_index)
    actual_base = _pointer("/events", actual_index)
    if expected["kind"] != actual["kind"]:
        differences.append(
            _difference(
                "events",
                "event_kind_changed",
                _pointer(expected_base, "kind"),
                _pointer(actual_base, "kind"),
                expected["kind"],
                actual["kind"],
            )
        )
    if expected["name"] != actual["name"]:
        differences.append(
            _difference(
                "events",
                "event_name_changed",
                _pointer(expected_base, "name"),
                _pointer(actual_base, "name"),
                expected["name"],
                actual["name"],
            )
        )
    _compare_json(
        _strip_diagnostics(expected["data"]),
        _strip_diagnostics(actual["data"]),
        expected_path=_pointer(expected_base, "data"),
        actual_path=_pointer(actual_base, "data"),
        section="events",
        differences=differences,
    )


def _compare_dependency_record(
    expected: Record,
    actual: Record,
    expected_index: int,
    actual_index: int,
    differences: list[Difference],
) -> None:
    expected_base = _pointer("/dependencies", expected_index)
    actual_base = _pointer("/dependencies", actual_index)
    if expected["kind"] != actual["kind"]:
        differences.append(
            _difference(
                "dependencies",
                "dependency_kind_changed",
                _pointer(expected_base, "kind"),
                _pointer(actual_base, "kind"),
                expected["kind"],
                actual["kind"],
            )
        )
    if expected["operation"] != actual["operation"]:
        differences.append(
            _difference(
                "dependencies",
                "dependency_operation_changed",
                _pointer(expected_base, "operation"),
                _pointer(actual_base, "operation"),
                expected["operation"],
                actual["operation"],
            )
        )
    _compare_json(
        expected["request"],
        actual["request"],
        expected_path=_pointer(expected_base, "request"),
        actual_path=_pointer(actual_base, "request"),
        section="dependencies",
        differences=differences,
    )

    expected_outcome = expected["outcome"]
    actual_outcome = actual["outcome"]
    expected_status = expected_outcome["status"]
    actual_status = actual_outcome["status"]
    if expected_status != actual_status:
        differences.append(
            _difference(
                "dependencies",
                "dependency_outcome_status_changed",
                _pointer(_pointer(expected_base, "outcome"), "status"),
                _pointer(_pointer(actual_base, "outcome"), "status"),
                expected_status,
                actual_status,
            )
        )
        return
    if expected_status == "returned":
        field_name = "response"
    elif expected_status == "errored":
        field_name = "error"
    else:
        raise SemanticValidationError("dependency outcome status must be returned or errored")
    _compare_json(
        expected_outcome[field_name],
        actual_outcome[field_name],
        expected_path=_pointer(_pointer(expected_base, "outcome"), field_name),
        actual_path=_pointer(_pointer(actual_base, "outcome"), field_name),
        section="dependencies",
        differences=differences,
    )


def compare_execution(
    *,
    original_observation: dict[str, Any],
    replay_observation: dict[str, Any],
    recorded_dependencies: list[dict[str, Any]],
    replay_dependencies: list[dict[str, Any]],
) -> ExecutionDiff:
    """Compare two portable executions without mutating either input."""
    canonicalize(original_observation)
    canonicalize(replay_observation)
    canonicalize(recorded_dependencies)
    canonicalize(replay_dependencies)

    expected_events = original_observation["events"]
    actual_events = replay_observation["events"]
    _validate_sequence(expected_events, "original events")
    _validate_sequence(actual_events, "replay events")
    _validate_sequence(recorded_dependencies, "recorded dependencies")
    _validate_sequence(replay_dependencies, "replay dependencies")

    execution_differences: list[Difference] = []
    dependency_differences = _compare_ordered_records(
        recorded_dependencies,
        replay_dependencies,
        domain="dependencies",
        projection=_dependency_projection,
        anchor=lambda record: (record["kind"], record["operation"]),
        compare_record=_compare_dependency_record,
    )
    event_differences = _compare_ordered_records(
        expected_events,
        actual_events,
        domain="events",
        projection=_event_projection,
        anchor=lambda record: (record["kind"], record["name"]),
        compare_record=_compare_event_record,
    )
    terminal_differences: list[Difference] = []

    expected_status = original_observation["execution_status"]
    actual_status = replay_observation["execution_status"]
    supported_statuses = {"completed", "errored", "cancelled"}
    if expected_status not in supported_statuses or actual_status not in supported_statuses:
        raise SemanticValidationError("execution_status must be completed, errored, or cancelled")
    if expected_status != actual_status:
        execution_differences.append(
            _difference(
                "execution",
                "execution_status_changed",
                "/execution_status",
                "/execution_status",
                expected_status,
                actual_status,
            )
        )

    _compare_json(
        _strip_diagnostics(original_observation["error"]),
        _strip_diagnostics(replay_observation["error"]),
        expected_path="/error",
        actual_path="/error",
        section="execution",
        differences=execution_differences,
    )
    _compare_json(
        _strip_diagnostics(original_observation["output"]),
        _strip_diagnostics(replay_observation["output"]),
        expected_path="/output",
        actual_path="/output",
        section="terminal",
        differences=terminal_differences,
    )

    sections = {
        "execution": execution_differences,
        "dependencies": dependency_differences,
        "events": event_differences,
        "terminal": terminal_differences,
    }
    differences = [item for section in sections.values() for item in section]
    document = {
        "format_version": "0.1.0",
        "matches": not differences,
        "policy": {
            "canonicalization": "RFC8785",
            "path_format": "RFC6901",
            "ignored_diagnostic_keys": sorted(_DIAGNOSTIC_KEYS),
        },
        "sections": {
            name: {"matches": not items, "difference_count": len(items)}
            for name, items in sections.items()
        },
        "first_divergences": {
            name: None if not items else items[0]["path"] for name, items in sections.items()
        },
        "differences": differences,
    }
    analysis_metadata = {
        "format_version": document["format_version"],
        "matches": document["matches"],
        "sections": document["sections"],
        "first_divergences": document["first_divergences"],
    }
    return ExecutionDiff(canonicalize(document), canonicalize(analysis_metadata))
