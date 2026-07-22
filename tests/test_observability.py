from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from traceforge import metrics
from traceforge.assembly import SQLiteAssemblyState
from traceforge.examples.weather_agent import run as weather_runner
from traceforge.kafka_runtime import capsule_events
from traceforge.kafka_worker import KafkaAssemblyWorker
from traceforge.observability import configure, current_correlation, message_context
from traceforge.replay import CallableFrameworkAdapter, replay_exact
from traceforge.store import JsonFileCapsuleStore

ROOT = Path(__file__).resolve().parents[1]
TRACE_ID = "00112233445566778899aabbccddeeff"
SPAN_ID = "0011223344556677"
TRACEPARENT = f"00-{TRACE_ID}-{SPAN_ID}-01"


class _Message:
    def __init__(self, event: dict[str, Any], headers: list[tuple[str, bytes]] | None) -> None:
        self._value = json.dumps(event).encode()
        self._headers = headers

    def value(self) -> bytes:
        return self._value

    def key(self) -> bytes:
        return b"capture-otel-test"

    def error(self) -> None:
        return None

    def headers(self) -> list[tuple[str, bytes]] | None:
        return self._headers


class _Consumer:
    def commit(self, message: Any, asynchronous: bool = False) -> None:
        assert message is not None and asynchronous is False

    def close(self) -> None:
        pass


class _Dlq:
    def produce(self, topic: str, **kwargs: Any) -> None:
        raise AssertionError((topic, kwargs))

    def poll(self, timeout: float) -> int:
        return 0

    def flush(self, timeout: float) -> int:
        return 0


def _recording_provider(monkeypatch: Any) -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "get_tracer", provider.get_tracer)
    return provider, exporter


def test_message_context_valid_missing_and_malformed_headers() -> None:
    with message_context([("traceparent", TRACEPARENT.encode())]):
        assert current_correlation() == {"trace_id": TRACE_ID, "span_id": SPAN_ID}
    assert current_correlation() is None

    for headers in (None, [("traceparent", b"malformed")]):
        with message_context(headers):
            assert current_correlation() is None
        assert current_correlation() is None


def test_capture_consume_assembly_and_seal_span_tree(monkeypatch: Any, tmp_path: Path) -> None:
    provider, exporter = _recording_provider(monkeypatch)
    capsule = JsonFileCapsuleStore().load(ROOT / "examples/weather/replay-capsule.json")
    events = capsule_events(capsule, "capture-otel-test")
    state = SQLiteAssemblyState(tmp_path / "state.sqlite3", tmp_path / "capsules")
    worker = KafkaAssemblyWorker(_Consumer(), _Dlq(), state, "dlq")
    headers = [("traceparent", TRACEPARENT.encode())]

    for event in events:
        assert worker.process_message(_Message(event, headers))

    spans = {item.name: item for item in exporter.get_finished_spans()}
    consume = spans["capture.consume"]
    assert format(consume.context.trace_id, "032x") == TRACE_ID
    assert spans["capsule.assemble"].parent.span_id == consume.context.span_id
    assert spans["capsule.seal"].parent.span_id == consume.context.span_id
    correlation = state.capture("capture-otel-test")
    assert correlation is not None
    assert correlation["trace_id"] == TRACE_ID
    assert correlation["span_id"] == format(consume.context.span_id, "016x")
    state.close()
    provider.shutdown()


def test_replay_is_separate_linked_trace_and_preserves_evidence(
    monkeypatch: Any,
) -> None:
    provider, exporter = _recording_provider(monkeypatch)
    store = JsonFileCapsuleStore()
    capsule = store.load(ROOT / "examples/weather/replay-capsule.json")
    spec = store.load(ROOT / "examples/weather/regression-spec.json")
    before = json.dumps(capsule, ensure_ascii=False, sort_keys=True).encode()

    result = replay_exact(
        capsule,
        CallableFrameworkAdapter(weather_runner),
        spec,
        correlation={"trace_id": TRACE_ID, "span_id": SPAN_ID},
    )

    replay = next(item for item in exporter.get_finished_spans() if item.name == "replay.execute")
    assert format(replay.context.trace_id, "032x") != TRACE_ID
    assert len(replay.links) == 1
    assert format(replay.links[0].context.trace_id, "032x") == TRACE_ID
    assert format(replay.links[0].context.span_id, "016x") == SPAN_ID
    assert result.regression is not None and result.regression.passed
    assert json.dumps(capsule, ensure_ascii=False, sort_keys=True).encode() == before
    provider.shutdown()


def test_observability_disabled_and_metric_labels_are_bounded(monkeypatch: Any) -> None:
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    assert configure("test-service") is None
    assert metrics.REPLAY is None or metrics.REPLAY._labelnames == ("result",)
    for collector in (
        metrics.CONSUMED,
        metrics.DUPLICATES,
        metrics.DLQ,
        metrics.SEALED,
        metrics.PROCESSING,
    ):
        assert collector is None or collector._labelnames == ()
