"""Bounded real HTTP gateway to Kafka to replay smoke workflow."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

from traceforge.examples.weather_agent import run
from traceforge.kafka_runtime import capsule_events
from traceforge.observability import (
    configure,
    current_correlation,
    last_replay_correlation,
    shutdown,
    span,
)
from traceforge.replay import CallableFrameworkAdapter, replay_exact
from traceforge.store import JsonFileCapsuleStore
from traceforge.validation import validate_capsule

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:18080/v1/capture-events"
TRACE_FILE = ROOT / ".traceforge-data/otel/traces.json"
SUMMARY_FILE = ROOT / ".traceforge-data/otel/verification-summary.json"


def post(
    body: bytes, content_type: str = "application/json", trace_headers: dict[str, str] | None = None
) -> int:
    headers = {"content-type": content_type, **(trace_headers or {})}
    request = urllib.request.Request(URL, body, headers, method="POST")
    try:
        return urllib.request.urlopen(request, timeout=5).status
    except urllib.error.HTTPError as exc:
        return exc.code


def _trace_spans(path: Path) -> list[tuple[str, dict[str, object]]]:
    spans: list[tuple[str, dict[str, object]]] = []
    for line in path.read_text().splitlines():
        document = json.loads(line)
        for resource_spans in document.get("resourceSpans", []):
            attributes = resource_spans.get("resource", {}).get("attributes", [])
            service = next(
                (
                    attribute["value"]["stringValue"]
                    for attribute in attributes
                    if attribute.get("key") == "service.name"
                ),
                "unknown",
            )
            for scope in resource_spans.get("scopeSpans", []):
                spans.extend((service, item) for item in scope.get("spans", []))
    return spans


def wait_for_sealed_capture_context(capture_trace_id: str) -> dict[str, str]:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if TRACE_FILE.is_file():
            capture = [
                (service, item)
                for service, item in _trace_spans(TRACE_FILE)
                if item.get("traceId") == capture_trace_id
            ]
            consume_ids = {
                item.get("spanId")
                for service, item in capture
                if service == "traceforge-capsule-worker" and item.get("name") == "capture.consume"
            }
            seal = next(
                (
                    item
                    for service, item in capture
                    if service == "traceforge-capsule-worker" and item.get("name") == "capsule.seal"
                ),
                None,
            )
            if seal is not None and seal.get("parentSpanId") in consume_ids:
                return {"trace_id": capture_trace_id, "span_id": str(seal["parentSpanId"])}
        time.sleep(0.25)
    raise RuntimeError("Collector did not expose the completed capture context in time")


def verify_collector(correlation: dict[str, str], replay_trace_id: str) -> dict[str, object]:
    capture_trace_id = correlation["trace_id"]
    deadline = time.monotonic() + 15
    spans: list[tuple[str, dict[str, object]]] = []
    expected = {
        "traceforge-ingest-gateway": {"capture.receive", "capture.validate", "capture.publish"},
        "traceforge-capsule-worker": {"capture.consume", "capsule.assemble", "capsule.seal"},
    }
    while time.monotonic() < deadline:
        if TRACE_FILE.is_file():
            spans = _trace_spans(TRACE_FILE)
            observed_during_wait: dict[str, set[str]] = {}
            for service, item in spans:
                if item.get("traceId") == capture_trace_id:
                    observed_during_wait.setdefault(service, set()).add(str(item.get("name")))
            replay_during_wait = [
                item
                for _, item in spans
                if item.get("traceId") == replay_trace_id and item.get("name") == "replay.execute"
            ]
            if all(
                names <= observed_during_wait.get(service, set())
                for service, names in expected.items()
            ) and any(
                link.get("traceId") == capture_trace_id
                for item in replay_during_wait
                for link in item.get("links", [])
            ):
                break
        time.sleep(0.25)
    capture = [
        (service, item) for service, item in spans if item.get("traceId") == capture_trace_id
    ]
    replay = [(service, item) for service, item in spans if item.get("traceId") == replay_trace_id]
    observed: dict[str, set[str]] = {}
    for service, item in capture:
        observed.setdefault(service, set()).add(str(item.get("name")))
    missing = {
        service: sorted(names - observed.get(service, set()))
        for service, names in expected.items()
        if names - observed.get(service, set())
    }
    if missing:
        raise RuntimeError(f"Collector is missing expected cross-service spans: {missing}")
    publish_ids = {
        item.get("spanId")
        for service, item in capture
        if service == "traceforge-ingest-gateway" and item.get("name") == "capture.publish"
    }
    consume_parents = {
        item.get("parentSpanId")
        for service, item in capture
        if service == "traceforge-capsule-worker" and item.get("name") == "capture.consume"
    }
    if not publish_ids.intersection(consume_parents):
        raise RuntimeError("worker spans do not descend from Kafka-propagated publish contexts")
    replay_span = next((item for _, item in replay if item.get("name") == "replay.execute"), None)
    if replay_span is None or not any(
        link.get("traceId") == capture_trace_id and link.get("spanId") == correlation["span_id"]
        for link in replay_span.get("links", [])
    ):
        raise RuntimeError("Collector replay span does not link to the capture trace")
    attribute_text = json.dumps(
        [item.get("attributes", []) for _, item in capture + replay], ensure_ascii=False
    ).lower()
    prohibited = {
        "authorization",
        "api_key",
        "bearer ",
        "kolkata",
        "umbrella",
        "light rain",
    }
    leaked = sorted(value for value in prohibited if value in attribute_text)
    if leaked:
        raise RuntimeError(f"sensitive or payload values found in span attributes: {leaked}")
    summary: dict[str, object] = {
        "capture_trace_id": capture_trace_id,
        "replay_trace_id": replay_trace_id,
        "replay_link_trace_id": capture_trace_id,
        "replay_link_span_id": correlation["span_id"],
        "kafka_parent_link": "passed",
        "services": {service: sorted(names) for service, names in observed.items()},
        "sensitive_attribute_scan": "passed",
    }
    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> int:
    provider = configure("traceforge-smoke-client")
    store = JsonFileCapsuleStore()
    source = store.load(ROOT / "examples/weather/replay-capsule.json")
    spec = store.load(ROOT / "examples/weather/regression-spec.json")
    capture_id = f"gateway-otel-smoke-{uuid4().hex[:12]}"
    events = capsule_events(source, capture_id)
    try:
        from opentelemetry import propagate

        with span("capture.smoke"):
            trace_headers: dict[str, str] = {}
            propagate.inject(trace_headers)
            capture_context = current_correlation()
            statuses = [
                post(json.dumps(event).encode(), trace_headers=trace_headers) for event in events
            ]
            if any(status != 202 for status in statuses):
                raise RuntimeError(f"unexpected POST statuses: {statuses}")
            target = ROOT / f".traceforge-data/capsules/{capture_id}.json"
            deadline = time.monotonic() + 30
            while not target.is_file() and time.monotonic() < deadline:
                time.sleep(0.25)

        sealed = store.load(target)
        validate_capsule(sealed)
        if not capture_context:
            raise RuntimeError("instrumented smoke requires enabled OpenTelemetry")
        correlation = wait_for_sealed_capture_context(capture_context["trace_id"])
        result = replay_exact(sealed, CallableFrameworkAdapter(run), spec, correlation=correlation)
        replay_context = last_replay_correlation()
        if result.regression is None or not result.regression.passed:
            raise RuntimeError("offline replay regression failed")
        if not replay_context:
            raise RuntimeError("telemetry did not produce capture and replay span identities")
        if capture_context["trace_id"] == replay_context["trace_id"]:
            raise RuntimeError("replay must use a separate trace")
        duplicate = [
            post(json.dumps(event).encode(), trace_headers=trace_headers) for event in events
        ]
        malformed = post(b"{")
        files = list(target.parent.glob(f"{capture_id}*.json"))
        shutdown(provider)
        provider = None
        collector = verify_collector(correlation, replay_context["trace_id"])
        output = {
            "accepted": statuses,
            "capture_id": capture_id,
            "capture_trace_id": capture_context["trace_id"],
            "duplicate": duplicate,
            "malformed": malformed,
            "capsules": len(files),
            "replay_link_trace_id": correlation["trace_id"],
            "replay_passed": True,
            "replay_trace_id": replay_context["trace_id"],
            "telemetry": collector,
            "telemetry_summary": str(SUMMARY_FILE),
        }
        print(json.dumps(output, sort_keys=True))
        return 0 if malformed == 400 and len(files) == 1 else 1
    finally:
        shutdown(provider)


if __name__ == "__main__":
    sys.exit(main())
