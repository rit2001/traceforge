from __future__ import annotations

import asyncio
import copy
import json
import threading
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from traceforge.assembly import AssemblyError, SQLiteAssemblyState
from traceforge.canonical import canonicalize, request_fingerprint
from traceforge.capture import CaptureSession
from traceforge.capture_events import sanitize_and_validate_event
from traceforge.dependencies import RecordedDependencyAdapter
from traceforge.diff import compare_execution
from traceforge.examples.portable_execution_spans import build_capsule, run
from traceforge.exceptions import (
    IntegrityError,
    SealingError,
    SemanticValidationError,
    StructuralValidationError,
)
from traceforge.kafka_runtime import capsule_events
from traceforge.replay import CallableFrameworkAdapter, replay_exact
from traceforge.sealing import seal_capsule
from traceforge.validation import validate_capsule, validate_integrity, validate_semantics

ROOT = Path(__file__).resolve().parents[1]


def _draft() -> dict[str, Any]:
    draft = build_capsule()
    draft.pop("integrity")
    return draft


def _session() -> CaptureSession:
    return CaptureSession(
        schema_version="0.3.0",
        capsule_id="span-capture",
        run_id="span-run",
        capture_kind="controlled_fixture",
        producer={"name": "traceforge-tests", "version": "0.5.0"},
        subject={
            "application": "span-tests",
            "revision": "test",
            "framework": "custom-python",
            "language": "Python",
        },
        operation="test",
        invocation_input={},
        recorded_at="2026-10-08T00:00:00Z",
    )


def test_replay_capsule_03_schema_is_valid_and_controlled_tree_is_attributed() -> None:
    schema = json.loads((ROOT / "schemas/replay-capsule-v0.3.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    capsule = build_capsule()

    validate_capsule(capsule)
    assert [span["execution_span_id"] for span in capsule["execution_spans"]] == [
        "weather-agent",
        "reasoning-step",
        "weather-lookup",
    ]
    assert capsule["execution_spans"][1]["parent_execution_span_id"] == "weather-agent"
    assert capsule["execution_spans"][2]["parent_execution_span_id"] == "weather-agent"
    assert capsule["dependencies"][0]["execution_span_id"] == "reasoning-step"
    assert capsule["dependencies"][1]["execution_span_id"] == "weather-lookup"
    assert capsule["original_observation"]["events"][0]["execution_span_id"] == ("weather-agent")


def test_capture_context_restores_parent_after_child_exception() -> None:
    session = _session()
    with session.execution_span("root", kind="agent", name="root", component="app"):
        with pytest.raises(RuntimeError, match="controlled"):
            with session.execution_span("child", kind="step", name="child", component="app"):
                raise RuntimeError("controlled")
        session.record_event("state", "recovered", {})

    draft = session.finish("completed", {})
    assert draft["original_observation"]["events"][0]["execution_span_id"] == "root"
    validate_capsule(seal_capsule(draft))


def test_capture_context_normal_exit_and_inner_caught_exception_preserve_nesting() -> None:
    session = _session()
    with session.execution_span("root", kind="agent", name="root", component="app"):
        with session.execution_span("first", kind="step", name="first", component="app"):
            try:
                raise ValueError("caught inside")
            except ValueError:
                session.record_event("state", "inside-child", {})
        with session.execution_span("second", kind="step", name="second", component="app"):
            session.record_event("state", "inside-sibling", {})

    draft = session.finish("completed", {})
    assert [event["execution_span_id"] for event in draft["original_observation"]["events"]] == [
        "first",
        "second",
    ]
    assert [span["parent_execution_span_id"] for span in draft["execution_spans"]] == [
        None,
        "root",
        "root",
    ]


def test_active_capture_stack_rejects_cross_thread_use() -> None:
    session = _session()
    failures: list[Exception] = []

    def use_session() -> None:
        try:
            session.record_event("state", "foreign-thread", {})
        except Exception as exc:  # asserted below
            failures.append(exc)

    with session.execution_span("root", kind="agent", name="root", component="app"):
        worker = threading.Thread(target=use_session)
        worker.start()
        worker.join()
    assert len(failures) == 1
    assert isinstance(failures[0], SemanticValidationError)
    assert "threads or async tasks" in str(failures[0])


def test_active_capture_stack_rejects_cross_async_task_use() -> None:
    async def exercise() -> Exception:
        session = _session()
        with session.execution_span("root", kind="agent", name="root", component="app"):

            async def use_session() -> Exception:
                try:
                    session.record_event("state", "foreign-task", {})
                except Exception as exc:  # returned for assertion
                    return exc
                raise AssertionError("foreign task unexpectedly recorded an event")

            return await asyncio.create_task(use_session())

    failure = asyncio.run(exercise())
    assert isinstance(failure, SemanticValidationError)
    assert "threads or async tasks" in str(failure)


def test_root_only_span_and_03_tool_attribution_are_valid() -> None:
    session = _session()
    with session.execution_span("root", kind="agent", name="root", component="app"):
        result = session.record_tool("lookup", {"item": 1}, lambda arguments: arguments)

    capsule = seal_capsule(session.finish("completed", result))
    assert capsule["execution_spans"] == [
        {
            "execution_span_id": "root",
            "parent_execution_span_id": None,
            "sequence": 1,
            "kind": "agent",
            "name": "root",
            "component": "app",
        }
    ]
    assert capsule["dependencies"][0]["kind"] == "tool"
    assert capsule["dependencies"][0]["execution_span_id"] == "root"


def test_smallest_valid_03_capsule_has_one_idle_root_and_terminal_output() -> None:
    session = _session()
    with session.execution_span("root", kind="agent", name="root", component="app"):
        pass

    capsule = seal_capsule(session.finish("completed", {"answer": "done"}))
    assert len(capsule["execution_spans"]) == 1
    assert capsule["dependencies"] == []
    assert capsule["original_observation"]["events"] == []
    assert capsule["original_observation"]["output"] == {"answer": "done"}
    validate_capsule(capsule)


@pytest.mark.parametrize("label", ["", "   ", "x" * 257, "line\nbreak", "control\x00"])
def test_capture_rejects_nonportable_span_labels(label: str) -> None:
    with pytest.raises(SemanticValidationError, match="non-blank portable label"):
        with _session().execution_span("root", kind=label, name="name", component="component"):
            pass


@pytest.mark.parametrize(
    "label", ["raisonnement-東京", 'quoted "label"', "path/like/label", "<span>text</span>"]
)
def test_portable_span_labels_are_untrusted_unicode_text(label: str) -> None:
    session = _session()
    with session.execution_span("root", kind="agent", name=label, component="app"):
        pass
    capsule = seal_capsule(session.finish("completed", None))
    assert capsule["execution_spans"][0]["name"] == label


@pytest.mark.parametrize("value", [object(), {"x": 1}, ["x"], ("x",), b"x", float("nan")])
def test_span_identifiers_and_labels_never_serialize_python_objects(value: Any) -> None:
    with pytest.raises(SemanticValidationError):
        with _session().execution_span(value, kind="agent", name="root", component="app"):
            pass
    with pytest.raises(SemanticValidationError):
        with _session().execution_span("root", kind=value, name="root", component="app"):
            pass


def test_capture_requires_explicit_active_span_and_closed_nesting() -> None:
    session = _session()
    with pytest.raises(SemanticValidationError, match="active execution span"):
        session.record_event("state", "outside", {})

    with session.execution_span("root", kind="agent", name="root", component="app"):
        with pytest.raises(SemanticValidationError, match="while an execution span is active"):
            session.finish("completed", {})


def test_capture_rejects_duplicate_invalid_and_pre_03_span_ids() -> None:
    session = _session()
    with pytest.raises(SemanticValidationError, match="valid stable portable identifier"):
        with session.execution_span("bad id", kind="step", name="bad", component="app"):
            pass
    with session.execution_span("root", kind="agent", name="root", component="app"):
        pass
    with pytest.raises(SemanticValidationError, match="duplicate"):
        with session.execution_span("root", kind="agent", name="root", component="app"):
            pass

    another = _session()
    with another.execution_span("root", kind="agent", name="root", component="app"):
        pass
    with pytest.raises(SemanticValidationError, match="exactly one root"):
        with another.execution_span("second", kind="agent", name="second", component="app"):
            pass

    with pytest.raises(SemanticValidationError, match="requires one root"):
        _session().finish("completed", {})

    with pytest.raises(SemanticValidationError, match="safe stable label"):
        with _session().execution_span(
            "root", kind="agent", name="root", component="api_key=known-secret"
        ):
            pass

    old = CaptureSession(
        capsule_id="old",
        run_id="old-run",
        capture_kind="controlled_fixture",
        producer={"name": "test", "version": "1"},
        subject={
            "application": "old",
            "revision": "1",
            "framework": "custom",
            "language": "Python",
        },
        operation="run",
        invocation_input={},
    )
    with pytest.raises(SemanticValidationError, match="schema_version '0.3.0'"):
        with old.execution_span("root", kind="agent", name="root", component="app"):
            pass


@pytest.mark.parametrize(
    "execution_span_id",
    ["", "   ", "x" * 129, "line\nbreak", "control\x00", "東京", '"quoted"', "path/id", "<id>"],
)
def test_portable_execution_span_identifier_grammar_is_bounded_and_ascii_safe(
    execution_span_id: str,
) -> None:
    with pytest.raises(SemanticValidationError, match="valid stable portable identifier"):
        with _session().execution_span(
            execution_span_id, kind="agent", name="root", component="app"
        ):
            pass


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda draft: draft["execution_spans"][1].update(parent_execution_span_id="missing"),
            "earlier",
        ),
        (
            lambda draft: draft["execution_spans"][1].update(
                parent_execution_span_id="reasoning-step"
            ),
            "self-parent",
        ),
        (
            lambda draft: draft["execution_spans"][0].update(
                parent_execution_span_id="weather-lookup"
            ),
            "one root",
        ),
        (
            lambda draft: draft["execution_spans"][1].update(execution_span_id="weather-agent"),
            "unique",
        ),
        (lambda draft: draft["execution_spans"][1].update(sequence=3), "sequence"),
        (
            lambda draft: draft["execution_spans"][1].update(parent_execution_span_id=None),
            "one root",
        ),
        (
            lambda draft: draft["dependencies"][0].update(execution_span_id="missing"),
            "reference an execution span",
        ),
        (
            lambda draft: draft["original_observation"]["events"][0].update(
                execution_span_id="missing"
            ),
            "reference an execution span",
        ),
        (
            lambda draft: draft["execution_spans"][0].update(name="   "),
            "non-blank and control-free",
        ),
        (
            lambda draft: draft["execution_spans"][0].update(component="line\nbreak"),
            "non-blank and control-free",
        ),
    ],
)
def test_span_semantics_fail_closed(change: Any, message: str) -> None:
    draft = _draft()
    change(draft)
    with pytest.raises(SealingError, match=message):
        seal_capsule(draft)


def test_cycle_is_rejected_by_single_root_and_earlier_parent_rules() -> None:
    capsule = build_capsule()
    capsule["execution_spans"][0]["parent_execution_span_id"] = "reasoning-step"
    capsule["execution_spans"][1]["parent_execution_span_id"] = "weather-agent"
    with pytest.raises(SemanticValidationError, match="one root"):
        validate_semantics(capsule)


def test_reordered_span_records_are_rejected() -> None:
    capsule = build_capsule()
    capsule["execution_spans"].reverse()
    with pytest.raises(SemanticValidationError, match="ordered and contiguous"):
        validate_semantics(capsule)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda draft: draft.update(execution_spans=[]), "should be non-empty"),
        (
            lambda draft: [
                span.update(sequence=span["sequence"] + 1) for span in draft["execution_spans"]
            ],
            "contiguous from 1",
        ),
        (
            lambda draft: draft["execution_spans"][1].update(
                parent_execution_span_id="weather-lookup"
            ),
            "earlier span",
        ),
    ],
)
def test_additional_root_and_order_invariants_fail_with_specific_errors(
    change: Any, message: str
) -> None:
    draft = _draft()
    change(draft)
    with pytest.raises(SealingError, match=message):
        seal_capsule(draft)


def test_deep_chain_and_many_siblings_are_valid_tree_shapes() -> None:
    for parents in (
        [None, *[f"span-{index - 1}" for index in range(1, 25)]],
        [None, *(["span-0"] * 24)],
    ):
        draft = _draft()
        draft["execution_spans"] = [
            {
                "execution_span_id": f"span-{index}",
                "parent_execution_span_id": parent,
                "sequence": index + 1,
                "kind": "step",
                "name": f"span {index}",
                "component": "test",
            }
            for index, parent in enumerate(parents)
        ]
        for dependency in draft["dependencies"]:
            dependency["execution_span_id"] = "span-0"
        for event in draft["original_observation"]["events"]:
            event["execution_span_id"] = "span-0"
        validate_capsule(seal_capsule(draft))


def test_attribution_may_reference_a_later_span_record_without_implying_chronology() -> None:
    draft = _draft()
    draft["dependencies"][0]["execution_span_id"] = "weather-lookup"
    draft["original_observation"]["events"][0]["execution_span_id"] = "weather-lookup"
    capsule = seal_capsule(draft)
    validate_capsule(capsule)


@pytest.mark.parametrize(
    "change",
    [
        lambda draft: draft["execution_spans"][0].update(execution_span_id="bad id"),
        lambda draft: (
            draft["execution_spans"][0].update(span_id="otel-looking-id"),
            draft["execution_spans"][0].pop("execution_span_id"),
        ),
        lambda draft: draft["execution_spans"][0].pop("component"),
        lambda draft: draft["dependencies"][0].pop("execution_span_id"),
        lambda draft: draft["original_observation"]["events"][0].pop("execution_span_id"),
    ],
)
def test_span_structure_rejects_invalid_or_missing_fields(change: Any) -> None:
    draft = _draft()
    change(draft)
    with pytest.raises(SealingError):
        seal_capsule(draft)


def test_unsupported_capsule_version_is_not_guessed() -> None:
    draft = _draft()
    draft["schema_version"] = "0.4.0"
    with pytest.raises(SealingError, match="unsupported schema_version"):
        seal_capsule(draft)


@pytest.mark.parametrize(
    "change",
    [
        lambda capsule: capsule["execution_spans"][0].update(execution_span_id="changed"),
        lambda capsule: capsule["execution_spans"][0].update(sequence=99),
        lambda capsule: capsule["execution_spans"][0].update(kind="changed"),
        lambda capsule: capsule["execution_spans"][0].update(name="changed"),
        lambda capsule: capsule["execution_spans"][0].update(component="changed"),
        lambda capsule: capsule["execution_spans"][2].update(
            parent_execution_span_id="reasoning-step"
        ),
        lambda capsule: capsule["dependencies"][0].update(execution_span_id="weather-lookup"),
        lambda capsule: capsule["original_observation"]["events"][0].update(
            execution_span_id="weather-lookup"
        ),
        lambda capsule: capsule["execution_spans"].pop(),
        lambda capsule: capsule["execution_spans"].append(
            {
                "execution_span_id": "extra",
                "parent_execution_span_id": "weather-agent",
                "sequence": 4,
                "kind": "step",
                "name": "extra",
                "component": "test",
            }
        ),
        lambda capsule: capsule["execution_spans"].reverse(),
        lambda capsule: capsule["execution_spans"][1].update(parent_execution_span_id=None),
    ],
)
def test_span_and_attribution_mutation_breaks_capsule_integrity(change: Any) -> None:
    capsule = build_capsule()
    change(capsule)
    with pytest.raises(IntegrityError, match="integrity.digest"):
        validate_integrity(capsule)


def test_sealing_breaks_aliases_and_rejects_non_json_values() -> None:
    draft = _draft()
    capsule = seal_capsule(draft)
    draft["execution_spans"][0]["name"] = "mutated-after-seal"
    assert capsule["execution_spans"][0]["name"] == "weather_agent"

    non_json = _draft()
    non_json["original_observation"]["events"][0]["data"] = object()
    with pytest.raises(SealingError, match="canonicalized"):
        seal_capsule(non_json)

    non_finite = _draft()
    non_finite["original_observation"]["events"][0]["data"] = float("inf")
    with pytest.raises(SealingError, match="canonicalized"):
        seal_capsule(non_finite)


def test_capture_finish_seal_and_transport_are_alias_isolated() -> None:
    event_data = {"nested": [{"value": "original"}]}
    tool_arguments = {"nested": [{"value": "original"}]}
    tool_result = {"nested": [{"value": "original"}]}
    output = {"nested": [{"value": "original"}]}
    session = _session()
    with session.execution_span("root", kind="agent", name="root", component="app"):
        session.record_event("state", "event", event_data)
        session.record_tool("tool", tool_arguments, lambda _arguments: tool_result)

    draft = session.finish("completed", output)
    event_data["nested"][0]["value"] = "caller-mutated"
    tool_arguments["nested"][0]["value"] = "caller-mutated"
    tool_result["nested"][0]["value"] = "caller-mutated"
    output["nested"][0]["value"] = "caller-mutated"
    assert draft["original_observation"]["events"][0]["data"]["nested"][0]["value"] == ("original")
    assert draft["dependencies"][0]["request"]["arguments"]["nested"][0]["value"] == ("original")
    assert (
        draft["dependencies"][0]["outcome"]["response"]["result"]["nested"][0]["value"]
        == "original"
    )
    assert draft["original_observation"]["output"]["nested"][0]["value"] == "original"

    capsule = seal_capsule(draft)
    draft["original_observation"]["events"][0]["data"]["nested"][0]["value"] = "draft-mutated"
    assert capsule["original_observation"]["events"][0]["data"]["nested"][0]["value"] == (
        "original"
    )

    events = capsule_events(capsule, "alias-isolation")
    events[1]["payload"]["name"] = "transport-mutated"
    assert capsule["execution_spans"][0]["name"] == "root"


def test_03_session_detaches_caller_owned_base_values_at_creation() -> None:
    producer = {"name": "original-producer", "version": "1"}
    subject = {
        "application": "original-application",
        "revision": "1",
        "framework": "custom-python",
        "language": "Python",
    }
    invocation_input = {"nested": ["original-input"]}
    session = CaptureSession(
        schema_version="0.3.0",
        capsule_id="base-aliases",
        run_id="base-aliases-run",
        capture_kind="controlled_fixture",
        producer=producer,
        subject=subject,
        operation="test",
        invocation_input=invocation_input,
        recorded_at="2026-10-08T00:00:00Z",
    )
    producer["name"] = "mutated-producer"
    subject["application"] = "mutated-application"
    invocation_input["nested"][0] = "mutated-input"
    with session.execution_span("root", kind="agent", name="root", component="app"):
        pass
    draft = session.finish("completed", None)
    assert draft["producer"]["name"] == "original-producer"
    assert draft["subject"]["application"] == "original-application"
    assert draft["invocation"]["input"]["nested"] == ["original-input"]


def test_exact_replay_validates_but_does_not_require_replay_span_ids() -> None:
    result = replay_exact(build_capsule(), CallableFrameworkAdapter(run))

    assert result.technical_status == "completed"
    assert result.deterministic_match is True
    assert result.execution_diff is not None
    assert result.execution_diff.to_dict()["matches"] is True
    assert "events[*].execution_span_id" in result.to_dict()["comparison"]["ignored_fields"]

    reassigned = _draft()
    reassigned["original_observation"]["events"][0]["execution_span_id"] = "weather-lookup"
    reassigned_result = replay_exact(seal_capsule(reassigned), CallableFrameworkAdapter(run))
    assert reassigned_result.deterministic_match is True
    assert reassigned_result.execution_diff.to_dict()["matches"] is True


def _run_with_event_data(
    event_data: Any,
) -> CallableFrameworkAdapter:
    def runner(invocation_input: Any, dependencies: Any) -> dict[str, Any]:
        observation = run(invocation_input, dependencies)
        observation["events"][0]["data"] = copy.deepcopy(event_data)
        return observation

    return CallableFrameworkAdapter(runner)


def test_replay_ignores_only_top_level_attribution_not_same_named_application_data() -> None:
    data = {
        "execution_span_id": "APPLICATION-DATA",
        "nested": {"execution_span_id": "APPLICATION-DATA-2"},
    }
    draft = _draft()
    draft["original_observation"]["events"][0]["data"] = copy.deepcopy(data)
    capsule = seal_capsule(draft)

    result = replay_exact(capsule, _run_with_event_data(data))
    assert result.deterministic_match is True
    assert result.execution_diff is not None
    assert result.execution_diff.to_dict()["matches"] is True

    changed = copy.deepcopy(data)
    changed["nested"]["execution_span_id"] = "CHANGED-APPLICATION-DATA"
    changed_result = replay_exact(capsule, _run_with_event_data(changed))
    assert changed_result.deterministic_match is False
    difference = changed_result.execution_diff.to_dict()["differences"][0]
    assert difference["path"] == "/events/0/data/nested/execution_span_id"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "changed-kind"),
        ("name", "changed-name"),
        ("data", {"changed": True}),
    ],
)
def test_replay_event_semantics_remain_compared(field: str, value: Any) -> None:
    def runner(invocation_input: Any, dependencies: Any) -> dict[str, Any]:
        observation = run(invocation_input, dependencies)
        observation["events"][0][field] = value
        return observation

    result = replay_exact(build_capsule(), CallableFrameworkAdapter(runner))
    assert result.deterministic_match is False
    assert result.execution_diff is not None
    assert result.execution_diff.to_dict()["sections"]["events"]["matches"] is False


@pytest.mark.parametrize(
    ("field", "value", "section"),
    [
        ("execution_status", "cancelled", "execution"),
        ("output", None, "terminal"),
        ("error", {"type": "Changed", "message": "changed", "data": None}, "execution"),
    ],
)
def test_replay_terminal_semantics_remain_compared(field: str, value: Any, section: str) -> None:
    def runner(invocation_input: Any, dependencies: Any) -> dict[str, Any]:
        observation = run(invocation_input, dependencies)
        observation[field] = value
        if field == "execution_status" and value == "cancelled":
            observation["output"] = None
        if field == "error":
            observation["execution_status"] = "errored"
            observation["output"] = None
        return observation

    result = replay_exact(build_capsule(), CallableFrameworkAdapter(runner))
    assert result.deterministic_match is False
    assert result.execution_diff is not None
    assert result.execution_diff.to_dict()["sections"][section]["matches"] is False


def test_replay_projection_and_returned_structures_do_not_mutate_capsule() -> None:
    capsule = build_capsule()
    before = canonicalize(capsule)
    result = replay_exact(capsule, CallableFrameworkAdapter(run))
    assert canonicalize(capsule) == before

    result.original_observation["events"][0]["execution_span_id"] = "mutated-result"
    result.replay_observation["events"][0]["data"] = {"mutated": True}
    diff = result.execution_diff.to_dict()
    diff["differences"].append({"mutated": True})
    assert canonicalize(capsule) == before


def test_execution_diff_ignores_attribution_but_compares_same_named_event_data() -> None:
    capsule = build_capsule()
    original = copy.deepcopy(capsule["original_observation"])
    replay = copy.deepcopy(original)
    replay["events"][0].pop("execution_span_id")
    assert (
        compare_execution(
            original_observation=original,
            replay_observation=replay,
            recorded_dependencies=[],
            replay_dependencies=[],
        ).to_dict()["matches"]
        is True
    )

    original["events"][0]["data"] = {"execution_span_id": "application-one"}
    replay["events"][0]["data"] = {"execution_span_id": "application-two"}
    document = compare_execution(
        original_observation=original,
        replay_observation=replay,
        recorded_dependencies=[],
        replay_dependencies=[],
    ).to_dict()
    assert document["differences"][0]["path"] == "/events/0/data/execution_span_id"


def test_dependency_attribution_does_not_change_fingerprint_or_replay_identity() -> None:
    capsule = build_capsule()
    dependency = capsule["dependencies"][0]
    assert dependency["request_fingerprint"] == request_fingerprint(dependency["request"])

    reassigned = _draft()
    reassigned["dependencies"][0]["execution_span_id"] = "weather-lookup"
    reassigned_capsule = seal_capsule(reassigned)
    changed_dependency = reassigned_capsule["dependencies"][0]
    assert changed_dependency["request_fingerprint"] == dependency["request_fingerprint"]

    old_session = CaptureSession(
        schema_version="0.2.0",
        capsule_id="old-fingerprint",
        run_id="old-fingerprint-run",
        capture_kind="controlled_fixture",
        producer={"name": "test", "version": "1"},
        subject={
            "application": "test",
            "revision": "1",
            "framework": "custom-python",
            "language": "Python",
        },
        operation="test",
        invocation_input={},
        recorded_at="2026-10-08T00:00:00Z",
    )
    old_session.record_model(
        dependency["operation"],
        dependency["request"],
        lambda _request: dependency["outcome"]["response"],
    )
    old_capsule = seal_capsule(old_session.finish("completed", None))
    assert (
        old_capsule["dependencies"][0]["request_fingerprint"] == dependency["request_fingerprint"]
    )

    for record in (dependency, changed_dependency):
        adapter = RecordedDependencyAdapter([record])
        outcome = adapter.invoke(record["kind"], record["operation"], record["request"])
        assert outcome == record["outcome"]
        adapter.assert_consumed()
        assert "execution_span_id" not in adapter.transcript[0]


def test_capture_event_03_dispatch_and_distributed_assembly(tmp_path: Path) -> None:
    capsule = build_capsule()
    events = capsule_events(capsule, "portable-span-capture")

    assert {event["schema_version"] for event in events} == {"0.3.0"}
    assert [event["event_type"] for event in events[1:4]] == [
        "execution_span_recorded",
        "execution_span_recorded",
        "execution_span_recorded",
    ]
    for event in events:
        sanitize_and_validate_event(event)

    state = SQLiteAssemblyState(tmp_path / "state.sqlite3", tmp_path / "capsules")
    for event in events:
        result = state.process(event)
    assert result.completed and result.capsule_path is not None
    assembled = json.loads(result.capsule_path.read_text())
    assert assembled == capsule
    state.close()


def test_capture_event_03_idempotency_conflicts_and_sequence_gaps(tmp_path: Path) -> None:
    events = capsule_events(build_capsule(), "delivery-rules")
    state = SQLiteAssemblyState(tmp_path / "state.sqlite3", tmp_path / "capsules")
    first = state.process(events[0])
    duplicate = state.process(copy.deepcopy(events[0]))
    assert first.duplicate is False
    assert duplicate.duplicate is True

    conflicting = copy.deepcopy(events[0])
    conflicting["payload"]["capsule_id"] = "different"
    with pytest.raises(AssemblyError, match="conflicting content"):
        state.process(conflicting)
    with pytest.raises(AssemblyError, match="expected sequence 2"):
        state.process(events[2])
    state.close()


def test_capture_event_versions_cannot_be_forged_or_mixed(tmp_path: Path) -> None:
    events = capsule_events(build_capsule(), "mixed-versions")
    forged = copy.deepcopy(events[1])
    forged["schema_version"] = "0.2.0"
    with pytest.raises(StructuralValidationError):
        sanitize_and_validate_event(forged)

    unsupported = copy.deepcopy(events[0])
    unsupported["schema_version"] = "0.4.0"
    with pytest.raises(StructuralValidationError, match="unsupported"):
        sanitize_and_validate_event(unsupported)

    state = SQLiteAssemblyState(tmp_path / "state.sqlite3", tmp_path / "capsules")
    state.process(events[0])
    mixed = copy.deepcopy(events[1])
    mixed["schema_version"] = "0.2.0"
    mixed["event_type"] = "dependency_recorded"
    with pytest.raises(AssemblyError, match="cannot mix"):
        state.process(mixed)
    state.close()


def test_capture_event_03_rejects_completion_observation_mismatch(tmp_path: Path) -> None:
    events = capsule_events(build_capsule(), "observation-mismatch")
    observation = next(event for event in events if event["event_type"] == "observation_recorded")
    events[-1]["payload"]["original_observation"]["events"][0]["name"] = "forged"
    assert observation["payload"]["name"] == "final_answer"
    state = SQLiteAssemblyState(tmp_path / "state.sqlite3", tmp_path / "capsules")
    for event in events[:-1]:
        state.process(event)
    with pytest.raises(AssemblyError, match="must match"):
        state.process(events[-1])
    assert state.capture("observation-mismatch")["completed"] is False
    state.close()


def test_distributed_assembly_rejects_unknown_span_attribution(tmp_path: Path) -> None:
    events = capsule_events(build_capsule(), "unknown-attribution")
    dependency = next(event for event in events if event["event_type"] == "dependency_recorded")
    dependency["payload"]["execution_span_id"] = "missing"
    state = SQLiteAssemblyState(tmp_path / "state.sqlite3", tmp_path / "capsules")
    for event in events[:-1]:
        state.process(event)
    with pytest.raises(SealingError, match="reference an execution span"):
        state.process(events[-1])
    assert state.capture("unknown-attribution")["completed"] is False
    state.close()


def test_distributed_assembly_rejects_unknown_event_attribution(tmp_path: Path) -> None:
    events = capsule_events(build_capsule(), "unknown-event-attribution")
    observation = next(event for event in events if event["event_type"] == "observation_recorded")
    observation["payload"]["execution_span_id"] = "missing"
    events[-1]["payload"]["original_observation"]["events"][0]["execution_span_id"] = "missing"
    state = SQLiteAssemblyState(tmp_path / "state.sqlite3", tmp_path / "capsules")
    for event in events[:-1]:
        state.process(event)
    with pytest.raises(SealingError, match="reference an execution span"):
        state.process(events[-1])
    state.close()


def test_core_span_contract_is_framework_neutral_and_separate_from_otel() -> None:
    core = "\n".join(
        (ROOT / path).read_text()
        for path in (
            "src/traceforge/capture.py",
            "src/traceforge/schema.py",
            "src/traceforge/validation.py",
            "src/traceforge/replay.py",
        )
    ).lower()
    for forbidden in ("langgraph", "langchain", "crewai", "autogen"):
        assert forbidden not in core
    assert "current_correlation" not in core
    assert "trace_id" not in core


def test_operational_otel_ids_are_not_copied_or_interpreted_as_evidence_ids() -> None:
    operational_span_id = "abc123abc123abcd"
    capsule = build_capsule()
    portable_ids = {span["execution_span_id"] for span in capsule["execution_spans"]}
    assert "weather-agent" in portable_ids
    assert operational_span_id not in portable_ids
    assert "trace_id" not in capsule
    assert "span_id" not in capsule
    assert all("span_id" not in span for span in capsule["execution_spans"])

    events = capsule_events(capsule, "otel-separation")
    span_event = next(event for event in events if event["event_type"] == "execution_span_recorded")
    assert span_event["payload"]["execution_span_id"] == "weather-agent"
    assert "span_id" not in span_event["payload"]


def test_capture_event_03_schema_is_meta_valid() -> None:
    schema = json.loads((ROOT / "schemas/capture-event-v0.3.schema.json").read_text())
    Draft202012Validator.check_schema(schema)


def test_capture_event_rejects_span_labels_that_sanitization_would_rewrite() -> None:
    event = json.loads(
        (ROOT / "schemas/fixtures/capture-events/valid-v0.3-execution-span.json").read_text()
    )
    event["payload"]["component"] = "token=known-secret"
    with pytest.raises(StructuralValidationError, match="safe stable values"):
        sanitize_and_validate_event(event)
