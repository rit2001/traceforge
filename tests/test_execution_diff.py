from __future__ import annotations

import copy
import importlib
import importlib.util
import inspect
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from traceforge.canonical import canonicalize
from traceforge.exceptions import IntegrityError, SemanticValidationError


@pytest.fixture
def diff_api() -> ModuleType:
    """Load the Issue #3 API; absence is the intentional RED-phase failure."""
    return importlib.import_module("traceforge.diff")


def _observation(
    *,
    status: str = "completed",
    events: list[dict[str, Any]] | None = None,
    output: Any = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "execution_status": status,
        "events": [] if events is None else events,
        "output": output,
        "error": error,
    }


def _event(
    sequence: int,
    *,
    kind: str = "step",
    name: str = "run",
    data: Any = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id or f"event-{sequence}",
        "sequence": sequence,
        "kind": kind,
        "name": name,
        "data": {} if data is None else data,
    }


def _returned(result: Any) -> dict[str, Any]:
    return {"status": "returned", "response": {"result": result}}


def _errored(
    error_type: str = "ControlledError",
    message: str = "controlled failure",
    data: Any = None,
) -> dict[str, Any]:
    return {
        "status": "errored",
        "error": {"type": error_type, "message": message, "data": data},
    }


def _dependency(
    sequence: int,
    *,
    kind: str = "tool",
    operation: str = "catalog.lookup",
    request: Any = None,
    outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "kind": kind,
        "operation": operation,
        "request": {"arguments": {"item_id": sequence}} if request is None else request,
        "outcome": _returned({"item_id": sequence}) if outcome is None else outcome,
    }


def _result(
    diff_api: ModuleType,
    *,
    original_observation: dict[str, Any] | None = None,
    replay_observation: dict[str, Any] | None = None,
    recorded_dependencies: list[dict[str, Any]] | None = None,
    replay_dependencies: list[dict[str, Any]] | None = None,
) -> Any:
    original = _observation() if original_observation is None else original_observation
    replay = copy.deepcopy(original) if replay_observation is None else replay_observation
    recorded = [] if recorded_dependencies is None else recorded_dependencies
    replayed = copy.deepcopy(recorded) if replay_dependencies is None else replay_dependencies
    result = diff_api.compare_execution(
        original_observation=original,
        replay_observation=replay,
        recorded_dependencies=recorded,
        replay_dependencies=replayed,
    )
    assert isinstance(result, diff_api.ExecutionDiff)
    return result


def _document(diff_api: ModuleType, **kwargs: Any) -> dict[str, Any]:
    return _result(diff_api, **kwargs).to_dict()


def _differences(document: dict[str, Any], code: str | None = None) -> list[dict[str, Any]]:
    differences = document["differences"]
    if code is None:
        return differences
    return [difference for difference in differences if difference["code"] == code]


def _only_difference(document: dict[str, Any], code: str) -> dict[str, Any]:
    differences = _differences(document, code)
    assert len(differences) == 1
    return differences[0]


def test_exact_match_has_empty_structured_diff(diff_api: ModuleType) -> None:
    observation = _observation(
        events=[_event(1, data={"state": "complete"})],
        output={"final_answer": "python.org"},
    )
    dependencies = [_dependency(1)]

    document = _document(
        diff_api,
        original_observation=observation,
        recorded_dependencies=dependencies,
    )

    assert document["format_version"] == "0.1.0"
    assert document["matches"] is True
    assert document["sections"] == {
        "execution": {"matches": True, "difference_count": 0},
        "dependencies": {"matches": True, "difference_count": 0},
        "events": {"matches": True, "difference_count": 0},
        "terminal": {"matches": True, "difference_count": 0},
    }
    assert document["first_divergences"] == {
        "execution": None,
        "dependencies": None,
        "events": None,
        "terminal": None,
    }
    assert document["differences"] == []


def test_execution_status_change_has_portable_snapshots(diff_api: ModuleType) -> None:
    original = _observation(status="completed")
    replay = _observation(
        status="errored",
        error={"type": "ControlledError", "message": "failure", "data": None},
    )

    document = _document(
        diff_api,
        original_observation=original,
        replay_observation=replay,
    )
    difference = _only_difference(document, "execution_status_changed")

    assert document["sections"]["execution"]["matches"] is False
    assert difference["section"] == "execution"
    assert difference["path"] == "/execution_status"
    assert difference["expected_path"] == "/execution_status"
    assert difference["actual_path"] == "/execution_status"
    assert difference["expected"] == {
        "present": True,
        "type": "string",
        "value": "completed",
    }
    assert difference["actual"] == {
        "present": True,
        "type": "string",
        "value": "errored",
    }


def test_terminal_scalar_change_uses_terminal_namespace(diff_api: ModuleType) -> None:
    document = _document(
        diff_api,
        original_observation=_observation(output={"final_answer": "python.org"}),
        replay_observation=_observation(output={"final_answer": "python.com"}),
    )
    difference = _only_difference(document, "value_changed")

    assert difference["section"] == "terminal"
    assert difference["path"] == "/output/final_answer"
    assert difference["expected"]["value"] == "python.org"
    assert difference["actual"]["value"] == "python.com"


def test_nested_object_change_has_exact_json_pointer(diff_api: ModuleType) -> None:
    document = _document(
        diff_api,
        original_observation=_observation(output={"result": {"metadata": {"source": "original"}}}),
        replay_observation=_observation(output={"result": {"metadata": {"source": "replay"}}}),
    )

    assert _only_difference(document, "value_changed")["path"] == ("/output/result/metadata/source")


def test_json_pointer_escapes_tilde_and_slash(diff_api: ModuleType) -> None:
    document = _document(
        diff_api,
        original_observation=_observation(output={"a~b/c": {"~key/": "original"}}),
        replay_observation=_observation(output={"a~b/c": {"~key/": "replay"}}),
    )

    assert _only_difference(document, "value_changed")["path"] == ("/output/a~0b~1c/~0key~1")


def test_missing_object_key_has_one_sided_location_and_snapshot(diff_api: ModuleType) -> None:
    document = _document(
        diff_api,
        original_observation=_observation(output={"kept": True, "missing": "value"}),
        replay_observation=_observation(output={"kept": True}),
    )
    difference = _only_difference(document, "object_key_missing")

    assert difference["path"] == "/output/missing"
    assert difference["expected_path"] == "/output/missing"
    assert difference["actual_path"] is None
    assert difference["expected"] == {
        "present": True,
        "type": "string",
        "value": "value",
    }
    assert difference["actual"] == {
        "present": False,
        "type": "missing",
        "value": None,
    }


def test_extra_object_key_has_one_sided_location_and_snapshot(diff_api: ModuleType) -> None:
    document = _document(
        diff_api,
        original_observation=_observation(output={"kept": True}),
        replay_observation=_observation(output={"kept": True, "extra": "value"}),
    )
    difference = _only_difference(document, "object_key_extra")

    assert difference["path"] == "/output/extra"
    assert difference["expected_path"] is None
    assert difference["actual_path"] == "/output/extra"
    assert difference["expected"] == {
        "present": False,
        "type": "missing",
        "value": None,
    }
    assert difference["actual"] == {
        "present": True,
        "type": "string",
        "value": "value",
    }


def test_array_item_change_uses_zero_based_index(diff_api: ModuleType) -> None:
    document = _document(
        diff_api,
        original_observation=_observation(output={"items": ["same", "original"]}),
        replay_observation=_observation(output={"items": ["same", "replay"]}),
    )

    assert _only_difference(document, "value_changed")["path"] == "/output/items/1"


@pytest.mark.parametrize(
    ("expected", "actual", "item_code", "item_path"),
    [
        ([1, 2], [1], "array_item_missing", "/output/items/1"),
        ([1], [1, 2], "array_item_extra", "/output/items/1"),
    ],
)
def test_array_length_change_also_reports_missing_or_extra_item(
    diff_api: ModuleType,
    expected: list[int],
    actual: list[int],
    item_code: str,
    item_path: str,
) -> None:
    document = _document(
        diff_api,
        original_observation=_observation(output={"items": expected}),
        replay_observation=_observation(output={"items": actual}),
    )

    assert _only_difference(document, "array_length_changed")["path"] == "/output/items"
    item_difference = _only_difference(document, item_code)
    assert item_difference["path"] == item_path
    if item_code == "array_item_missing":
        assert item_difference["expected_path"] == item_path
        assert item_difference["actual_path"] is None
    else:
        assert item_difference["expected_path"] is None
        assert item_difference["actual_path"] == item_path


def test_boolean_and_number_are_distinct_json_types(diff_api: ModuleType) -> None:
    document = _document(
        diff_api,
        original_observation=_observation(output={"value": True}),
        replay_observation=_observation(output={"value": 1}),
    )
    difference = _only_difference(document, "type_changed")

    assert difference["path"] == "/output/value"
    assert difference["expected"]["type"] == "boolean"
    assert difference["actual"]["type"] == "number"


def test_integer_and_equivalent_float_follow_rfc8785_number_semantics(
    diff_api: ModuleType,
) -> None:
    assert canonicalize(1) == canonicalize(1.0)

    document = _document(
        diff_api,
        original_observation=_observation(output={"value": 1}),
        replay_observation=_observation(output={"value": 1.0}),
    )

    assert document["matches"] is True
    assert document["differences"] == []


@pytest.mark.parametrize(
    "unsupported",
    [
        pytest.param({"not", "json"}, id="set"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(2**53, id="unsafe-integer"),
    ],
)
def test_unsupported_values_are_rejected_without_stringification(
    diff_api: ModuleType, unsupported: Any
) -> None:
    original = _observation(output={"value": unsupported})
    replay = copy.deepcopy(original)

    with pytest.raises(IntegrityError, match="RFC 8785"):
        _result(
            diff_api,
            original_observation=original,
            replay_observation=replay,
        )


def test_changed_event_compares_only_generic_fields(diff_api: ModuleType) -> None:
    original = [_event(1, kind="phase", name="prepare", data={"value": "original"})]
    replay = [_event(1, kind="step", name="execute", data={"value": "replay"})]

    document = _document(
        diff_api,
        original_observation=_observation(events=original),
        replay_observation=_observation(events=replay),
    )

    assert _only_difference(document, "event_kind_changed")["path"] == "/events/0/kind"
    assert _only_difference(document, "event_name_changed")["path"] == "/events/0/name"
    assert _only_difference(document, "value_changed")["path"] == "/events/0/data/value"


def test_missing_event_does_not_cascade_into_downstream_changes(diff_api: ModuleType) -> None:
    first = _event(1, name="first", data={"value": 1})
    missing = _event(2, name="missing", data={"value": 2})
    last = _event(3, name="last", data={"value": 3})
    replay_last = copy.deepcopy(last)
    replay_last["sequence"] = 2

    document = _document(
        diff_api,
        original_observation=_observation(events=[first, missing, last]),
        replay_observation=_observation(events=[copy.deepcopy(first), replay_last]),
    )

    assert [item["code"] for item in document["differences"]] == ["event_missing"]
    difference = document["differences"][0]
    assert difference["expected_path"] == "/events/1"
    assert difference["actual_path"] is None


def test_extra_event_does_not_cascade_into_downstream_changes(diff_api: ModuleType) -> None:
    first = _event(1, name="first", data={"value": 1})
    last = _event(2, name="last", data={"value": 3})
    replay_last = copy.deepcopy(last)
    replay_last["sequence"] = 3

    document = _document(
        diff_api,
        original_observation=_observation(events=[first, last]),
        replay_observation=_observation(
            events=[copy.deepcopy(first), _event(2, name="extra"), replay_last]
        ),
    )

    assert [item["code"] for item in document["differences"]] == ["event_extra"]
    difference = document["differences"][0]
    assert difference["expected_path"] is None
    assert difference["actual_path"] == "/events/1"


def test_pure_event_reorder_emits_one_reorder_only(diff_api: ModuleType) -> None:
    first = _event(1, name="first", data={"value": 1})
    second = _event(2, name="second", data={"value": 2})
    replay_second = copy.deepcopy(second)
    replay_second["sequence"] = 1
    replay_first = copy.deepcopy(first)
    replay_first["sequence"] = 2

    document = _document(
        diff_api,
        original_observation=_observation(events=[first, second]),
        replay_observation=_observation(events=[replay_second, replay_first]),
    )

    assert [item["code"] for item in document["differences"]] == ["event_reordered"]
    difference = document["differences"][0]
    assert difference["path"] == "/events"
    assert difference["expected_path"] == "/events"
    assert difference["actual_path"] == "/events"


def test_swapping_indistinguishable_duplicate_events_is_not_a_reorder(
    diff_api: ModuleType,
) -> None:
    expected = [
        _event(1, name="duplicate", data={"same": True}, event_id="event-a"),
        _event(2, name="duplicate", data={"same": True}, event_id="event-b"),
    ]
    actual = [
        _event(1, name="duplicate", data={"same": True}, event_id="event-b"),
        _event(2, name="duplicate", data={"same": True}, event_id="event-a"),
    ]

    document = _document(
        diff_api,
        original_observation=_observation(events=expected),
        replay_observation=_observation(events=actual),
    )

    assert document["matches"] is True
    assert document["differences"] == []


def test_equal_length_lcs_tie_advances_expected_side(diff_api: ModuleType) -> None:
    expected_first = _event(1, name="first", data={"value": 1})
    expected_second = _event(2, name="second", data={"value": 2})
    actual_second = copy.deepcopy(expected_second)
    actual_second["sequence"] = 1
    actual_first = copy.deepcopy(expected_first)
    actual_first["sequence"] = 2

    document = _document(
        diff_api,
        original_observation=_observation(events=[expected_first, expected_second]),
        replay_observation=_observation(
            events=[
                actual_second,
                actual_first,
                _event(3, name="third", data={"value": 3}),
            ]
        ),
    )

    assert [
        (item["code"], item["expected_path"], item["actual_path"])
        for item in document["differences"]
    ] == [
        ("event_missing", "/events/0", None),
        ("event_extra", None, "/events/1"),
        ("event_extra", None, "/events/2"),
    ]
    assert document["differences"][0]["expected"]["value"]["name"] == "first"
    assert document["differences"][1]["actual"]["value"]["name"] == "first"
    assert document["differences"][2]["actual"]["value"]["name"] == "third"


def test_ambiguous_event_gap_reports_missing_and_extra_without_pairing(
    diff_api: ModuleType,
) -> None:
    expected = [
        _event(1, kind="step", name="duplicate", data={"value": "expected-a"}),
        _event(2, kind="step", name="duplicate", data={"value": "expected-b"}),
    ]
    actual = [
        _event(1, kind="step", name="duplicate", data={"value": "actual-a"}),
        _event(2, kind="step", name="duplicate", data={"value": "actual-b"}),
    ]

    document = _document(
        diff_api,
        original_observation=_observation(events=expected),
        replay_observation=_observation(events=actual),
    )
    codes = [item["code"] for item in document["differences"]]

    assert codes == ["event_missing", "event_missing", "event_extra", "event_extra"]
    assert "value_changed" not in codes
    assert "event_reordered" not in codes


def test_unique_event_anchor_can_compare_different_indices_without_move_claim(
    diff_api: ModuleType,
) -> None:
    expected = [
        _event(1, name="unique", data={"value": "expected"}),
        _event(2, name="duplicate", data={"value": "expected-a"}),
        _event(3, name="duplicate", data={"value": "expected-b"}),
    ]
    actual = [
        _event(1, name="duplicate", data={"value": "actual-a"}),
        _event(2, name="unique", data={"value": "actual"}),
        _event(3, name="duplicate", data={"value": "actual-b"}),
    ]

    document = _document(
        diff_api,
        original_observation=_observation(events=expected),
        replay_observation=_observation(events=actual),
    )
    changed = _only_difference(document, "value_changed")
    codes = {item["code"] for item in document["differences"]}

    assert changed["path"] == "/events/0/data/value"
    assert changed["expected_path"] == "/events/0/data/value"
    assert changed["actual_path"] == "/events/1/data/value"
    assert "event_moved" not in codes
    assert "event_reordered" not in codes
    assert {"event_missing", "event_extra"} <= codes


def test_changed_dependency_kind_is_explicit(diff_api: ModuleType) -> None:
    document = _document(
        diff_api,
        recorded_dependencies=[_dependency(1, kind="model")],
        replay_dependencies=[_dependency(1, kind="tool")],
    )

    assert _only_difference(document, "dependency_kind_changed")["path"] == ("/dependencies/0/kind")


def test_changed_dependency_operation_is_explicit(diff_api: ModuleType) -> None:
    document = _document(
        diff_api,
        recorded_dependencies=[_dependency(1, operation="catalog.lookup")],
        replay_dependencies=[_dependency(1, operation="catalog.search")],
    )

    assert _only_difference(document, "dependency_operation_changed")["path"] == (
        "/dependencies/0/operation"
    )


def test_changed_dependency_request_is_recursively_compared(diff_api: ModuleType) -> None:
    document = _document(
        diff_api,
        recorded_dependencies=[
            _dependency(1, request={"arguments": {"query": {"term": "python"}}})
        ],
        replay_dependencies=[
            _dependency(1, request={"arguments": {"query": {"term": "python language"}}})
        ],
    )

    assert _only_difference(document, "value_changed")["path"] == (
        "/dependencies/0/request/arguments/query/term"
    )


def test_changed_dependency_returned_value_is_recursively_compared(
    diff_api: ModuleType,
) -> None:
    document = _document(
        diff_api,
        recorded_dependencies=[_dependency(1, outcome=_returned({"value": "original"}))],
        replay_dependencies=[_dependency(1, outcome=_returned({"value": "replay"}))],
    )

    assert _only_difference(document, "value_changed")["path"] == (
        "/dependencies/0/outcome/response/result/value"
    )


def test_returned_versus_errored_dependency_changes_outcome_status(
    diff_api: ModuleType,
) -> None:
    document = _document(
        diff_api,
        recorded_dependencies=[_dependency(1, outcome=_returned({"ok": True}))],
        replay_dependencies=[_dependency(1, outcome=_errored())],
    )

    difference = _only_difference(document, "dependency_outcome_status_changed")
    assert difference["path"] == "/dependencies/0/outcome/status"
    assert difference["expected"]["value"] == "returned"
    assert difference["actual"]["value"] == "errored"


def test_changed_dependency_error_compares_only_portable_error_fields(
    diff_api: ModuleType,
) -> None:
    document = _document(
        diff_api,
        recorded_dependencies=[
            _dependency(
                1,
                outcome=_errored("OriginalError", "original", {"retryable": False}),
            )
        ],
        replay_dependencies=[
            _dependency(
                1,
                outcome=_errored("ReplayError", "replay", {"retryable": True}),
            )
        ],
    )

    assert {item["path"] for item in _differences(document, "value_changed")} == {
        "/dependencies/0/outcome/error/type",
        "/dependencies/0/outcome/error/message",
        "/dependencies/0/outcome/error/data/retryable",
    }


def test_missing_dependency_is_reported(diff_api: ModuleType) -> None:
    first = _dependency(1, operation="first")
    missing = _dependency(2, operation="missing")
    last = _dependency(3, operation="last")
    replay_last = copy.deepcopy(last)
    replay_last["sequence"] = 2

    document = _document(
        diff_api,
        recorded_dependencies=[first, missing, last],
        replay_dependencies=[copy.deepcopy(first), replay_last],
    )
    difference = _only_difference(document, "dependency_missing")

    assert [item["code"] for item in document["differences"]] == ["dependency_missing"]
    assert difference["path"] == "/dependencies/1"
    assert difference["expected_path"] == "/dependencies/1"
    assert difference["actual_path"] is None


def test_extra_dependency_is_reported(diff_api: ModuleType) -> None:
    first = _dependency(1, operation="first")
    last = _dependency(2, operation="last")
    replay_last = copy.deepcopy(last)
    replay_last["sequence"] = 3

    document = _document(
        diff_api,
        recorded_dependencies=[first, last],
        replay_dependencies=[copy.deepcopy(first), _dependency(2, operation="extra"), replay_last],
    )
    difference = _only_difference(document, "dependency_extra")

    assert [item["code"] for item in document["differences"]] == ["dependency_extra"]
    assert difference["path"] == "/dependencies/1"
    assert difference["expected_path"] is None
    assert difference["actual_path"] == "/dependencies/1"


def test_pure_dependency_reorder_emits_one_reorder_only(diff_api: ModuleType) -> None:
    first = _dependency(1, operation="first")
    second = _dependency(2, operation="second")
    replay_second = copy.deepcopy(second)
    replay_second["sequence"] = 1
    replay_first = copy.deepcopy(first)
    replay_first["sequence"] = 2

    document = _document(
        diff_api,
        recorded_dependencies=[first, second],
        replay_dependencies=[replay_second, replay_first],
    )

    assert [item["code"] for item in document["differences"]] == ["dependency_reordered"]
    difference = document["differences"][0]
    assert difference["path"] == "/dependencies"
    assert difference["expected_path"] == "/dependencies"
    assert difference["actual_path"] == "/dependencies"


def test_ambiguous_dependency_gap_reports_missing_and_extra_without_pairing(
    diff_api: ModuleType,
) -> None:
    expected = [
        _dependency(1, operation="duplicate", request={"value": "expected-a"}),
        _dependency(2, operation="duplicate", request={"value": "expected-b"}),
    ]
    actual = [
        _dependency(1, operation="duplicate", request={"value": "actual-a"}),
        _dependency(2, operation="duplicate", request={"value": "actual-b"}),
    ]

    document = _document(
        diff_api,
        recorded_dependencies=expected,
        replay_dependencies=actual,
    )
    codes = [item["code"] for item in document["differences"]]

    assert codes == [
        "dependency_missing",
        "dependency_missing",
        "dependency_extra",
        "dependency_extra",
    ]
    assert "value_changed" not in codes
    assert "dependency_reordered" not in codes


def test_unique_dependency_anchor_can_compare_different_indices_without_move_claim(
    diff_api: ModuleType,
) -> None:
    expected = [
        _dependency(
            1,
            operation="unique",
            request={"value": "expected"},
            outcome=_returned({"stable": True}),
        ),
        _dependency(2, operation="duplicate", request={"value": "expected-a"}),
        _dependency(3, operation="duplicate", request={"value": "expected-b"}),
    ]
    actual = [
        _dependency(1, operation="duplicate", request={"value": "actual-a"}),
        _dependency(
            2,
            operation="unique",
            request={"value": "actual"},
            outcome=_returned({"stable": True}),
        ),
        _dependency(3, operation="duplicate", request={"value": "actual-b"}),
    ]

    document = _document(
        diff_api,
        recorded_dependencies=expected,
        replay_dependencies=actual,
    )
    changed = _only_difference(document, "value_changed")
    codes = {item["code"] for item in document["differences"]}

    assert changed["path"] == "/dependencies/0/request/value"
    assert changed["expected_path"] == "/dependencies/0/request/value"
    assert changed["actual_path"] == "/dependencies/1/request/value"
    assert "dependency_moved" not in codes
    assert "dependency_reordered" not in codes
    assert {"dependency_missing", "dependency_extra"} <= codes


@pytest.mark.parametrize(
    ("record_kind", "sequences"),
    [
        ("dependency", [0]),
        ("dependency", [2]),
        ("dependency", [1, 1]),
        ("event", [0]),
        ("event", [2]),
        ("event", [1, 1]),
    ],
)
def test_noncontiguous_or_position_mismatched_sequences_are_rejected(
    diff_api: ModuleType, record_kind: str, sequences: list[int]
) -> None:
    dependencies: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    if record_kind == "dependency":
        dependencies = [_dependency(sequence) for sequence in sequences]
    else:
        events = [
            _event(sequence, event_id=f"event-{index}") for index, sequence in enumerate(sequences)
        ]

    with pytest.raises(SemanticValidationError, match="sequence"):
        _result(
            diff_api,
            original_observation=_observation(events=events),
            replay_observation=_observation(events=copy.deepcopy(events)),
            recorded_dependencies=dependencies,
            replay_dependencies=copy.deepcopy(dependencies),
        )


def test_first_divergence_is_separate_for_every_section(diff_api: ModuleType) -> None:
    original = _observation(
        status="completed",
        events=[_event(1, data={"value": "original"})],
        output={"final_answer": "original"},
    )
    replay = _observation(
        status="errored",
        events=[_event(1, data={"value": "replay"})],
        output=None,
        error={"type": "ControlledError", "message": "failure", "data": None},
    )

    document = _document(
        diff_api,
        original_observation=original,
        replay_observation=replay,
        recorded_dependencies=[_dependency(1, request={"value": "original"})],
        replay_dependencies=[_dependency(1, request={"value": "replay"})],
    )

    assert document["first_divergences"] == {
        "execution": "/execution_status",
        "dependencies": "/dependencies/0/request/value",
        "events": "/events/0/data/value",
        "terminal": "/output",
    }
    assert "first_divergence" not in document
    section_order = [item["section"] for item in document["differences"]]
    assert section_order == sorted(
        section_order,
        key={"execution": 0, "dependencies": 1, "events": 2, "terminal": 3}.get,
    )


def test_repeated_comparison_has_identical_canonical_bytes(diff_api: ModuleType) -> None:
    original = _observation(
        events=[_event(1, data={"b": 2, "a": 1})],
        output={"answer": "original"},
    )
    replay = _observation(
        events=[_event(1, data={"b": 3, "a": 1})],
        output={"answer": "replay"},
    )

    serialized = {
        canonicalize(
            _document(
                diff_api,
                original_observation=copy.deepcopy(original),
                replay_observation=copy.deepcopy(replay),
            )
        )
        for _ in range(5)
    }

    assert len(serialized) == 1


def test_dictionary_insertion_order_does_not_change_result_bytes(diff_api: ModuleType) -> None:
    original_a = _observation(output={"outer": {"z": 1, "a": 2}})
    replay_a = _observation(output={"outer": {"a": 2, "z": 1}})
    original_b = _observation(output={"outer": {"a": 2, "z": 1}})
    replay_b = _observation(output={"outer": {"z": 1, "a": 2}})

    first = _document(
        diff_api,
        original_observation=original_a,
        replay_observation=replay_a,
    )
    second = _document(
        diff_api,
        original_observation=original_b,
        replay_observation=replay_b,
    )

    assert first["matches"] is True
    assert second["matches"] is True
    assert canonicalize(first) == canonicalize(second)


def test_comparison_does_not_mutate_any_input(diff_api: ModuleType) -> None:
    original = _observation(
        events=[_event(1, data={"nested": [1, 2]})],
        output={"answer": "original"},
    )
    replay = _observation(
        events=[_event(1, data={"nested": [1, 3]})],
        output={"answer": "replay"},
    )
    recorded = [_dependency(1, request={"nested": {"value": "original"}})]
    replayed = [_dependency(1, request={"nested": {"value": "replay"}})]
    before = copy.deepcopy((original, replay, recorded, replayed))

    _result(
        diff_api,
        original_observation=original,
        replay_observation=replay,
        recorded_dependencies=recorded,
        replay_dependencies=replayed,
    )

    assert (original, replay, recorded, replayed) == before


def test_result_exports_are_alias_isolated(diff_api: ModuleType) -> None:
    original = _observation(output={"answer": {"value": "original"}})
    replay = _observation(output={"answer": {"value": "replay"}})
    original_before = copy.deepcopy(original)
    replay_before = copy.deepcopy(replay)
    result = _result(
        diff_api,
        original_observation=original,
        replay_observation=replay,
    )

    first = result.to_dict()
    second = result.to_dict()
    assert first is not second
    assert first["differences"] is not second["differences"]

    first["differences"][0]["expected"]["value"] = "mutated export"
    third = result.to_dict()

    assert third == second
    assert original == original_before
    assert replay == replay_before


def test_framework_looking_values_are_opaque_json(diff_api: ModuleType) -> None:
    original = _observation(
        events=[
            _event(
                1,
                kind="chat_node",
                name="ToolMessage",
                data={"framework_value": "StateGraph"},
            )
        ]
    )
    replay = copy.deepcopy(original)
    replay["events"][0]["data"]["framework_value"] = "ordinary string"

    document = _document(
        diff_api,
        original_observation=original,
        replay_observation=replay,
    )

    assert [item["code"] for item in document["differences"]] == ["value_changed"]
    assert document["differences"][0]["path"] == "/events/0/data/framework_value"


def test_only_approved_diagnostic_keys_are_ignored(diff_api: ModuleType) -> None:
    original_output = {
        "duration_ms": 1,
        "recorded_at": "original",
        "timestamp": "original",
        "started_at": "original",
        "finished_at": "original",
        "value": "same",
    }
    replay_output = {
        "duration_ms": 2,
        "recorded_at": "replay",
        "timestamp": "replay",
        "started_at": "replay",
        "finished_at": "replay",
        "value": "same",
    }

    ignored = _document(
        diff_api,
        original_observation=_observation(output=original_output),
        replay_observation=_observation(output=replay_output),
    )
    assert ignored["matches"] is True
    assert set(ignored["policy"]["ignored_diagnostic_keys"]) == {
        "duration_ms",
        "recorded_at",
        "timestamp",
        "started_at",
        "finished_at",
    }

    original_output["elapsed_ms"] = 1
    replay_output["elapsed_ms"] = 2
    not_ignored = _document(
        diff_api,
        original_observation=_observation(output=original_output),
        replay_observation=_observation(output=replay_output),
    )
    assert _only_difference(not_ignored, "value_changed")["path"] == "/output/elapsed_ms"


def test_approved_diagnostic_keys_are_ignored_recursively(diff_api: ModuleType) -> None:
    original_output = {
        "result": {
            "metadata": {
                "duration_ms": 1,
                "payload": {"recorded_at": "original", "value": "same"},
            }
        }
    }
    replay_output = copy.deepcopy(original_output)
    replay_output["result"]["metadata"]["duration_ms"] = 999
    replay_output["result"]["metadata"]["payload"]["recorded_at"] = "replay"

    ignored = _document(
        diff_api,
        original_observation=_observation(output=original_output),
        replay_observation=_observation(output=replay_output),
    )
    assert ignored["matches"] is True
    assert ignored["differences"] == []

    replay_output["result"]["metadata"]["payload"]["value"] = "changed"
    compared = _document(
        diff_api,
        original_observation=_observation(output=original_output),
        replay_observation=_observation(output=replay_output),
    )
    assert [item["code"] for item in compared["differences"]] == ["value_changed"]
    assert compared["differences"][0]["path"] == "/output/result/metadata/payload/value"


def test_diff_contract_has_no_regression_input_or_result(diff_api: ModuleType) -> None:
    parameters = inspect.signature(diff_api.compare_execution).parameters
    document = _document(diff_api)

    assert "regression" not in parameters
    assert "regression_spec" not in parameters
    assert "regression" not in document


def test_dependency_difference_is_not_an_execution_status_difference(
    diff_api: ModuleType,
) -> None:
    document = _document(
        diff_api,
        original_observation=_observation(status="completed"),
        replay_observation=_observation(status="completed"),
        recorded_dependencies=[_dependency(1, request={"value": "expected"})],
        replay_dependencies=[_dependency(1, request={"value": "actual"})],
    )

    assert document["sections"]["execution"] == {
        "matches": True,
        "difference_count": 0,
    }
    assert document["first_divergences"]["execution"] is None
    assert "technical_status" not in document
    assert not _differences(document, "execution_status_changed")
    assert _only_difference(document, "value_changed")["section"] == "dependencies"


def test_core_diff_source_has_no_framework_specific_dependencies() -> None:
    spec = importlib.util.find_spec("traceforge.diff")
    if spec is None:
        return
    assert spec.origin is not None
    source = Path(spec.origin).read_text(encoding="utf-8").lower()

    prohibited = (
        "langgraph",
        "langchain",
        "crewai",
        "stategraph",
        "toolmessage",
        "aimessage",
    )
    assert not {term for term in prohibited if term in source}
