from __future__ import annotations

from typing import Any

from traceforge import CaptureSession, seal_capsule, validate_capsule
from traceforge.capture import BestEffortRedactionScanner


def _session(input_value: Any = None) -> CaptureSession:
    return CaptureSession(
        capsule_id="capture-test-1",
        run_id="run-capture-1",
        capture_kind="controlled_fixture",
        producer={"name": "tests", "version": "0.1.0"},
        subject={
            "application": "captured-app",
            "revision": "test",
            "framework": "tool-calling",
            "language": "Python",
        },
        operation="capture",
        invocation_input={} if input_value is None else input_value,
        recorded_at="2026-07-19T00:00:00Z",
    )


def test_scanner_removes_headers_keys_and_secret_query_parameters() -> None:
    result = BestEffortRedactionScanner().scan(
        {
            "api_key": "synthetic-sensitive-value",
            "url": "https://invalid.example/data?place=Kolkata&token=synthetic",
            "headers": {
                "content-type": "application/json",
                "authorization": "synthetic",
                "cookie": "synthetic",
                "x-extra": "not-retained",
            },
        }
    )
    assert "api_key" not in result.value
    assert "token=" not in result.value["url"]
    assert result.value["headers"] == {"content-type": "application/json"}
    assert len(result.actions) == 5


def test_capture_records_success_error_and_no_derived_fields() -> None:
    session = _session({"token": "should-not-persist", "question": "weather"})
    returned = session.record_model(
        "generate",
        {"model": "synthetic", "payload": {"api_key": "should-not-persist"}},
        lambda request: {"payload": {"content": request["model"]}},
    )

    def fail(request: Any) -> dict[str, Any]:
        del request
        raise RuntimeError(
            "controlled failure api_key=should-not-persist Bearer should-not-persist"
        )

    errored = session.record_http(
        "GET",
        {
            "method": "GET",
            "url": "https://invalid.example/weather?api_key=should-not-persist",
            "headers": {"authorization": "should-not-persist"},
            "body": None,
        },
        fail,
    )
    session.record_event("node", "failed", {"token": "should-not-persist", "safe": True})
    draft = session.finish(
        "errored",
        None,
        {"type": "RuntimeError", "message": "controlled failure", "data": None},
    )

    assert returned["status"] == "returned"
    assert errored["status"] == "errored"
    assert "request_fingerprint" not in draft["dependencies"][0]
    assert "integrity" not in draft
    assert "should-not-persist" not in repr(draft)
    assert draft["dependencies"][1]["request"]["headers"] == {}
    validate_capsule(seal_capsule(draft))
