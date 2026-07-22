from __future__ import annotations

from typing import Any

from traceforge.kafka import KafkaEventPublisher


def _event() -> dict[str, Any]:
    return {
        "schema_version": "0.2.0",
        "event_id": "event-1",
        "capture_id": "capture-1",
        "sequence": 1,
        "event_type": "capture_started",
        "occurred_at": "2026-07-19T12:00:00Z",
        "producer": {"name": "test", "version": "0.2.0"},
        "payload": {"token": "synthetic-secret", "safe": True},
    }


class FakeProducer:
    def __init__(self, full: bool = False) -> None:
        self.full = full
        self.calls: list[dict[str, Any]] = []
        self.flush_calls = 0

    def produce(self, topic: str, **kwargs: Any) -> None:
        if self.full:
            raise BufferError
        self.calls.append({"topic": topic, **kwargs})

    def poll(self, timeout: float) -> int:
        assert timeout == 0
        return 0

    def flush(self, timeout: float) -> int:
        self.flush_calls += 1
        assert timeout == 0.25
        return 0


def test_publisher_sanitizes_keys_and_enqueues_without_flush() -> None:
    producer = FakeProducer()
    publisher = KafkaEventPublisher(producer)
    result = publisher.publish(_event())
    assert result.status == "accepted"
    assert producer.calls[0]["key"] == b"capture-1"
    assert b"synthetic-secret" not in producer.calls[0]["value"]
    assert producer.flush_calls == 0
    producer.calls[0]["on_delivery"](None, object())
    assert publisher.completed_deliveries == 1


def test_full_queue_is_reported_without_raising() -> None:
    publisher = KafkaEventPublisher(FakeProducer(full=True))
    assert publisher.publish(_event()).status == "dropped"
    assert publisher.dropped_events == 1


def test_shutdown_flush_is_bounded() -> None:
    producer = FakeProducer()
    assert KafkaEventPublisher(producer).close(0.25) == 0
    assert producer.flush_calls == 1
