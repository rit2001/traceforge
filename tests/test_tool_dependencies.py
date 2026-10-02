from __future__ import annotations

from copy import deepcopy
from inspect import signature
from typing import Any

import pytest

from traceforge import (
    BestEffortRedactionScanner,
    CaptureSession,
    DependencyAdapter,
    UnreplayableCaptureError,
    invoke_recorded_tool,
)
from traceforge.canonical import request_fingerprint
from traceforge.exceptions import (
    DependencyMismatchError,
    MissingDependencyError,
    SealingError,
    SemanticValidationError,
    UnexpectedDependencyError,
    UnsafeToolArgumentsError,
    UnsupportedToolFailureError,
)
from traceforge.replay import CallableFrameworkAdapter, replay_exact
from traceforge.sealing import seal_capsule
from traceforge.validation import validate_capsule


def _session(
    *,
    capsule_id: str = "tool-capsule",
    scanner: BestEffortRedactionScanner | None = None,
) -> CaptureSession:
    return CaptureSession(
        schema_version="0.2.0",
        capsule_id=capsule_id,
        run_id=f"{capsule_id}-run",
        capture_kind="controlled_fixture",
        producer={"name": "traceforge-tests", "version": "0.5.0"},
        subject={
            "application": "tool-boundary-tests",
            "revision": "test",
            "framework": "Python",
            "language": "Python",
        },
        operation="run_tool",
        invocation_input={"value": "safe"},
        recorded_at="2026-10-01T00:00:00Z",
        scanner=scanner,
    )


def _observation(output: Any) -> dict[str, Any]:
    return {
        "execution_status": "completed",
        "events": [],
        "output": output,
        "error": None,
    }


def _tool_dependency(
    *,
    sequence: int = 1,
    operation: str = "catalog.lookup",
    arguments: Any = None,
    result: Any = None,
) -> dict[str, Any]:
    return {
        "dependency_id": f"dependency-{sequence}",
        "sequence": sequence,
        "kind": "tool",
        "operation": operation,
        "request": {"arguments": {} if arguments is None else arguments},
        "outcome": {
            "status": "returned",
            "response": {"result": result},
        },
        "duration_ms": 0,
    }


def _v020_draft(capsule_draft: dict[str, Any]) -> dict[str, Any]:
    draft = deepcopy(capsule_draft)
    draft["schema_version"] = "0.2.0"
    return draft


def test_v010_capsule_still_validates(capsule_draft: dict[str, Any]) -> None:
    capsule = seal_capsule(capsule_draft)
    assert capsule["schema_version"] == "0.1.0"
    validate_capsule(capsule)


def test_v010_exact_replay_still_works(capsule_draft: dict[str, Any]) -> None:
    capsule = seal_capsule(capsule_draft)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        recorded = capsule["dependencies"][0]
        dependencies.invoke(recorded["kind"], recorded["operation"], recorded["request"])
        return deepcopy(capsule["original_observation"])

    result = replay_exact(capsule, CallableFrameworkAdapter(runner))
    assert result.technical_status == "completed"
    assert result.deterministic_match is True


def test_v010_tool_dependency_is_rejected(capsule_draft: dict[str, Any]) -> None:
    capsule_draft["dependencies"] = [
        _tool_dependency(arguments={"item_id": 1}, result={"name": "safe item"})
    ]
    with pytest.raises(SealingError):
        seal_capsule(capsule_draft)


def test_schema_dispatch_does_not_guess_when_version_is_missing(
    capsule_draft: dict[str, Any],
) -> None:
    capsule_draft.pop("schema_version")
    with pytest.raises(SealingError, match="schema_version"):
        seal_capsule(capsule_draft)


def test_v010_capture_refuses_tool_before_execution() -> None:
    session = CaptureSession(
        capsule_id="v010-tool-refusal",
        run_id="v010-tool-refusal-run",
        capture_kind="controlled_fixture",
        producer={"name": "traceforge-tests", "version": "0.5.0"},
        subject={
            "application": "tool-boundary-tests",
            "revision": "test",
            "framework": "Python",
            "language": "Python",
        },
        operation="run_tool",
        invocation_input={},
        recorded_at="2026-10-01T00:00:00Z",
    )
    called = False

    def executor(arguments: Any) -> Any:
        nonlocal called
        called = True
        return arguments

    with pytest.raises(SemanticValidationError, match="schema_version '0.2.0'"):
        session.record_tool("catalog.lookup", {"item_id": 1}, executor)
    assert called is False


def test_v020_model_dependency_validates(capsule_draft: dict[str, Any]) -> None:
    validate_capsule(seal_capsule(_v020_draft(capsule_draft)))


def test_v020_http_dependency_validates(capsule_draft: dict[str, Any]) -> None:
    draft = _v020_draft(capsule_draft)
    draft["dependencies"] = [
        {
            "dependency_id": "dependency-1",
            "sequence": 1,
            "kind": "http",
            "operation": "GET",
            "request": {
                "method": "GET",
                "url": "https://invalid.example/items/1",
                "headers": {"content-type": "application/json"},
                "body": None,
            },
            "outcome": {
                "status": "returned",
                "response": {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": {"id": 1},
                },
            },
            "duration_ms": 0,
        }
    ]
    validate_capsule(seal_capsule(draft))


def test_v020_tool_dependency_validates(capsule_draft: dict[str, Any]) -> None:
    draft = _v020_draft(capsule_draft)
    draft["dependencies"] = [
        _tool_dependency(arguments={"item_id": 1}, result={"name": "safe item"})
    ]
    validate_capsule(seal_capsule(draft))


def test_result_unchanged_by_sanitization_is_recorded() -> None:
    session = _session()

    result = session.record_tool(
        "catalog.lookup",
        {"item_id": 1, "api_key": "known-secret"},
        lambda arguments: {
            "item_id": arguments["item_id"],
            "value": "safe",
        },
        sanitizer=lambda arguments: {"item_id": arguments["item_id"]},
    )
    capsule = seal_capsule(session.finish("completed", result))

    assert capsule["dependencies"][0]["request"] == {"arguments": {"item_id": 1}}
    assert capsule["dependencies"][0]["outcome"]["response"]["result"] == {
        "item_id": 1,
        "value": "safe",
    }
    assert "known-secret" not in repr(capsule)


def test_capture_returns_original_live_result() -> None:
    session = _session()
    produced = {"value": "safe"}

    captured_return = session.record_tool(
        "catalog.lookup",
        {"item_id": 1},
        lambda arguments: produced,
    )
    capsule = seal_capsule(session.finish("completed", captured_return))
    persisted_result = capsule["dependencies"][0]["outcome"]["response"]["result"]

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        return _observation(invoke_recorded_tool(dependencies, "catalog.lookup", {"item_id": 1}))

    replayed = replay_exact(capsule, CallableFrameworkAdapter(runner))
    replay_return = replayed.replay_observation["output"]

    assert captured_return is produced
    assert captured_return == {"value": "safe"}
    assert replay_return == persisted_result
    assert replay_return == captured_return


def test_result_changing_sanitization_marks_capture_unreplayable() -> None:
    session = _session()
    produced = {"value": "safe", "access_token": "synthetic-sensitive-result"}

    captured_return = session.record_tool(
        "catalog.lookup",
        {"item_id": 1},
        lambda arguments: produced,
    )

    assert captured_return is produced
    with pytest.raises(UnreplayableCaptureError, match="exact-replay evidence"):
        session.finish("completed", {"application": "continued"})


def test_unreplayable_capture_finish_fails_closed() -> None:
    session = _session()
    session.record_tool(
        "catalog.lookup",
        {"item_id": 1},
        lambda arguments: {"authorization": "Bearer synthetic-sensitive-result"},
    )

    with pytest.raises(UnreplayableCaptureError):
        session.finish("completed", {"application": "completed"})


def test_unreplayable_result_is_not_present_in_capsule_draft() -> None:
    session = _session()
    sensitive_value = "synthetic-sensitive-result"
    session.record_tool(
        "catalog.lookup",
        {"item_id": 1},
        lambda arguments: {"access_token": sensitive_value},
    )

    assert session._dependencies == []
    assert sensitive_value not in repr(session.__dict__)
    with pytest.raises(UnreplayableCaptureError):
        session.finish("completed", {"application": "completed"})


def test_sensitive_raw_result_not_present_in_error_message() -> None:
    session = _session()
    sensitive_value = "synthetic-sensitive-result"
    session.record_tool(
        "catalog.lookup",
        {"item_id": 1},
        lambda arguments: {"token": sensitive_value},
    )

    with pytest.raises(UnreplayableCaptureError) as captured:
        session.finish("completed", {"application": "completed"})
    assert sensitive_value not in str(captured.value)


def test_result_capture_failure_does_not_change_live_tool_success() -> None:
    session = _session()
    side_effects: list[str] = []
    produced = {"value": "safe", "client_secret": "synthetic-sensitive-result"}

    def executor(arguments: Any) -> Any:
        del arguments
        side_effects.append("executed")
        return produced

    captured_return = session.record_tool("side.effect", {"value": 1}, executor)

    assert side_effects == ["executed"]
    assert captured_return is produced
    with pytest.raises(UnreplayableCaptureError):
        session.finish("completed", {"application": "continued"})


def test_non_json_tool_result_marks_capture_unreplayable() -> None:
    session = _session()
    produced = object()

    captured_return = session.record_tool(
        "catalog.lookup",
        {"item_id": 1},
        lambda arguments: produced,
    )

    assert captured_return is produced
    assert session._dependencies == []
    with pytest.raises(UnreplayableCaptureError):
        session.finish("completed", {"application": "continued"})


def test_custom_scanner_is_rejected_before_tool_execution() -> None:
    class CustomScanner(BestEffortRedactionScanner):
        policy_version = "application-custom-v1"

    session = _session(scanner=CustomScanner())
    executor_called = False

    def executor(arguments: Any) -> Any:
        nonlocal executor_called
        executor_called = True
        return arguments

    with pytest.raises(SemanticValidationError, match="standard scanner"):
        session.record_tool("catalog.lookup", {"item_id": 1}, executor)
    assert executor_called is False


def test_public_tool_integration_api() -> None:
    import traceforge

    assert traceforge.CaptureSession is CaptureSession
    assert traceforge.DependencyAdapter is DependencyAdapter
    assert traceforge.invoke_recorded_tool is invoke_recorded_tool
    assert traceforge.UnreplayableCaptureError is UnreplayableCaptureError
    assert not hasattr(traceforge, "sanitize_tool_arguments")


def test_tool_request_fingerprint_is_stable() -> None:
    request_a = {"arguments": {"nested": {"b": 2, "a": 1}}}
    request_b = {"arguments": {"nested": {"a": 1, "b": 2}}}
    assert request_fingerprint(request_a) == request_fingerprint(request_b)


def test_exact_replay_returns_recorded_tool_result() -> None:
    session = _session()
    captured = session.record_tool(
        "catalog.lookup", {"item_id": 1}, lambda arguments: {"id": arguments["item_id"]}
    )
    capsule = seal_capsule(session.finish("completed", captured))

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        return _observation(invoke_recorded_tool(dependencies, "catalog.lookup", {"item_id": 1}))

    result = replay_exact(capsule, CallableFrameworkAdapter(runner))
    assert result.replay_observation["output"] == {"id": 1}


def test_exact_replay_never_calls_live_tool() -> None:
    session = _session()
    session.record_tool("side.effect", {"value": 1}, lambda arguments: arguments["value"] + 1)
    capsule = seal_capsule(session.finish("completed", 2))
    live_called = False

    def live_tool(arguments: Any) -> Any:
        nonlocal live_called
        live_called = True
        return arguments

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        assert callable(live_tool)
        return _observation(invoke_recorded_tool(dependencies, "side.effect", {"value": 1}))

    result = replay_exact(capsule, CallableFrameworkAdapter(runner))
    assert result.replay_observation["output"] == 2
    assert live_called is False
    assert tuple(signature(invoke_recorded_tool).parameters) == (
        "dependencies",
        "operation",
        "arguments",
        "sanitizer",
    )


def test_tool_argument_change_fails_closed() -> None:
    session = _session()
    session.record_tool("catalog.lookup", {"item_id": 1}, lambda arguments: arguments)
    capsule = seal_capsule(session.finish("completed", {"item_id": 1}))

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        invoke_recorded_tool(dependencies, "catalog.lookup", {"item_id": 2})
        return _observation(None)

    with pytest.raises(DependencyMismatchError, match="request mismatch"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))


def test_missing_tool_fixture_fails_closed(capsule_draft: dict[str, Any]) -> None:
    draft = _v020_draft(capsule_draft)
    draft["dependencies"] = []
    capsule = seal_capsule(draft)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        invoke_recorded_tool(dependencies, "catalog.lookup", {"item_id": 1})
        return _observation(None)

    with pytest.raises(UnexpectedDependencyError, match="no recorded fixture remains"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))


def test_reordered_tool_call_fails_closed(capsule_draft: dict[str, Any]) -> None:
    draft = _v020_draft(capsule_draft)
    tool = _tool_dependency(sequence=2, arguments={"item_id": 1}, result={"name": "safe item"})
    draft["dependencies"].append(tool)
    capsule = seal_capsule(draft)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        invoke_recorded_tool(dependencies, "catalog.lookup", {"item_id": 1})
        return _observation(None)

    with pytest.raises(DependencyMismatchError, match="kind mismatch"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))


def test_unused_tool_fixture_fails_replay(capsule_draft: dict[str, Any]) -> None:
    draft = _v020_draft(capsule_draft)
    draft["dependencies"] = [
        _tool_dependency(arguments={"item_id": 1}, result={"name": "safe item"})
    ]
    capsule = seal_capsule(draft)

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation, dependencies
        return _observation(None)

    with pytest.raises(MissingDependencyError, match="expected tool catalog.lookup"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))


def test_sensitive_identity_argument_is_not_silently_collapsed() -> None:
    executor_called = False

    def executor(arguments: Any) -> Any:
        nonlocal executor_called
        executor_called = True
        return arguments

    for value in ("identity-a", "identity-b"):
        with pytest.raises(UnsafeToolArgumentsError, match="deterministic sanitizer"):
            _session(capsule_id=f"tool-{value}").record_tool(
                "identity.lookup", {"access_token": value}, executor
            )
    assert executor_called is False


def test_unsafe_sensitive_identity_capture_fails_closed() -> None:
    session = _session()
    with pytest.raises(UnsafeToolArgumentsError, match="before tool execution"):
        session.record_tool(
            "identity.lookup",
            {"authorization": "Bearer known-secret", "account": "one"},
            lambda arguments: arguments,
        )
    assert session.finish("completed", None)["dependencies"] == []


def test_explicit_deterministic_sanitizer_preserves_safe_identity() -> None:
    references = {"identity-a": "account-a", "identity-b": "account-b"}

    def sanitizer(arguments: Any) -> Any:
        return {"account_ref": references[arguments["access_token"]]}

    fingerprints: list[str] = []
    for index, value in enumerate(("identity-a", "identity-b"), start=1):
        session = _session(capsule_id=f"tool-safe-{index}")
        session.record_tool(
            "identity.lookup",
            {"access_token": value},
            lambda arguments: {"found": bool(arguments)},
            sanitizer=sanitizer,
        )
        capsule = seal_capsule(session.finish("completed", {"found": True}))
        dependency = capsule["dependencies"][0]
        assert value not in repr(capsule)
        fingerprints.append(dependency["request_fingerprint"])
    assert fingerprints[0] != fingerprints[1]


def test_mutating_sanitizer_cannot_corrupt_caller_or_live_tool_arguments() -> None:
    original = {
        "account_ref": "account-a",
        "access_token": "synthetic-sensitive-input",
        "items": [1, 2],
    }
    expected = deepcopy(original)
    sanitizer_inputs: list[dict[str, Any]] = []
    sanitizer_initial_values: list[dict[str, Any]] = []
    live_arguments: list[dict[str, Any]] = []

    def mutating_sanitizer(arguments: dict[str, Any]) -> dict[str, Any]:
        sanitizer_inputs.append(arguments)
        sanitizer_initial_values.append(deepcopy(arguments))
        arguments.pop("access_token")
        arguments["items"].append("sanitizer-only")
        return {
            "account_ref": arguments["account_ref"],
            "items": arguments["items"][:-1],
        }

    def executor(arguments: dict[str, Any]) -> dict[str, bool]:
        live_arguments.append(deepcopy(arguments))
        arguments["items"].append("executor-only")
        return {"ok": True}

    session = _session()
    session.record_tool(
        "catalog.lookup",
        original,
        executor,
        sanitizer=mutating_sanitizer,
    )

    assert original == expected
    assert sanitizer_initial_values == [expected, expected]
    assert sanitizer_inputs[0] is not sanitizer_inputs[1]
    assert sanitizer_inputs[0] is not original
    assert sanitizer_inputs[1] is not original
    assert live_arguments == [expected]


def test_shared_sanitizer_return_cannot_defeat_determinism_check() -> None:
    shared_result: dict[str, str] = {}
    call_count = 0
    executor_called = False

    def sanitizer(arguments: Any) -> dict[str, str]:
        nonlocal call_count
        del arguments
        call_count += 1
        shared_result["account_ref"] = f"account-{call_count}"
        return shared_result

    def executor(arguments: Any) -> Any:
        nonlocal executor_called
        executor_called = True
        return arguments

    with pytest.raises(UnsafeToolArgumentsError, match="different identities"):
        _session().record_tool(
            "catalog.lookup",
            {"account": "safe"},
            executor,
            sanitizer=sanitizer,
        )
    assert executor_called is False


def test_recorded_timeout_preserves_catch_control_flow() -> None:
    session = _session()

    def timeout(arguments: Any) -> Any:
        del arguments
        raise TimeoutError("controlled timeout")

    try:
        session.record_tool("remote.wait", {"seconds": 1}, timeout)
    except TimeoutError as exc:
        captured_output = {
            "fallback": True,
            "exact_type": type(exc) is TimeoutError,
            "message": str(exc),
            "args": list(exc.args),
        }
    capsule = seal_capsule(session.finish("completed", captured_output))

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        del invocation
        try:
            invoke_recorded_tool(dependencies, "remote.wait", {"seconds": 1})
        except TimeoutError as exc:
            return _observation(
                {
                    "fallback": True,
                    "exact_type": type(exc) is TimeoutError,
                    "message": str(exc),
                    "args": list(exc.args),
                }
            )
        return _observation({"fallback": False})

    result = replay_exact(capsule, CallableFrameworkAdapter(runner))
    assert result.deterministic_match is True


def test_timeout_subclass_is_not_treated_as_safe_builtin() -> None:
    class DerivedTimeoutError(TimeoutError):
        pass

    session = _session()

    def fail(arguments: Any) -> Any:
        del arguments
        raise DerivedTimeoutError("derived timeout")

    with pytest.raises(DerivedTimeoutError):
        session.record_tool("remote.wait", {"seconds": 1}, fail)
    capsule = seal_capsule(session.finish("completed", {"fallback": True}))
    assert (
        capsule["dependencies"][0]["outcome"]["error"]["type"] == "unsupported:DerivedTimeoutError"
    )
    runner_called = False

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        nonlocal runner_called
        del invocation, dependencies
        runner_called = True
        return _observation(None)

    with pytest.raises(UnsupportedToolFailureError, match="DerivedTimeoutError"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))
    assert runner_called is False


def test_unsupported_recorded_tool_failure_stops_before_runner(
    capsule_draft: dict[str, Any],
) -> None:
    draft = _v020_draft(capsule_draft)
    dependency = _tool_dependency(arguments={"value": 1})
    dependency["outcome"] = {
        "status": "errored",
        "error": {"type": "ApplicationSpecificError", "message": "unsafe", "data": None},
    }
    draft["dependencies"] = [dependency]
    capsule = seal_capsule(draft)
    runner_called = False

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        nonlocal runner_called
        del invocation, dependencies
        runner_called = True
        return _observation(None)

    with pytest.raises(UnsupportedToolFailureError, match="ApplicationSpecificError"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))
    assert runner_called is False


def test_same_named_custom_timeout_is_not_treated_as_safe_builtin() -> None:
    custom_timeout = type("TimeoutError", (Exception,), {})
    session = _session()

    def fail(arguments: Any) -> Any:
        del arguments
        raise custom_timeout("custom timeout")

    with pytest.raises(custom_timeout):
        session.record_tool("remote.wait", {"seconds": 1}, fail)
    capsule = seal_capsule(session.finish("completed", {"fallback": True}))
    assert capsule["dependencies"][0]["outcome"]["error"]["type"] == "unsupported:TimeoutError"
    runner_called = False

    def runner(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
        nonlocal runner_called
        del invocation, dependencies
        runner_called = True
        return _observation(None)

    with pytest.raises(UnsupportedToolFailureError, match="unsupported:TimeoutError"):
        replay_exact(capsule, CallableFrameworkAdapter(runner))
    assert runner_called is False
