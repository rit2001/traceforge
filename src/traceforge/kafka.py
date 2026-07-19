"""Optional fail-soft Kafka capture-event publisher."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from traceforge.capture_events import sanitize_and_validate_event


class ProducerLike(Protocol):
    def produce(self, topic: str, **kwargs: Any) -> None: ...
    def poll(self, timeout: float) -> int: ...
    def flush(self, timeout: float) -> int: ...


@dataclass(frozen=True)
class PublishResult:
    status: Literal["accepted", "dropped", "failed"]
    detail: str


class KafkaEventPublisher:
    """Enqueue validated events; broker delivery remains asynchronous."""

    def __init__(self, producer: ProducerLike, topic: str = "traceforge.capture.v0") -> None:
        self._producer = producer
        self._topic = topic
        self.completed_deliveries = 0
        self.failed_deliveries = 0
        self.dropped_events = 0

    def _delivered(self, error: Any, message: Any) -> None:
        del message
        if error is None:
            self.completed_deliveries += 1
        else:
            self.failed_deliveries += 1

    def publish(self, event: dict[str, Any]) -> PublishResult:
        try:
            safe = sanitize_and_validate_event(event)
            self._producer.produce(
                self._topic,
                key=safe["capture_id"].encode(),
                value=json.dumps(safe, separators=(",", ":"), sort_keys=True).encode(),
                on_delivery=self._delivered,
            )
            self._producer.poll(0)
            return PublishResult("accepted", "queued for asynchronous delivery")
        except BufferError:
            self.dropped_events += 1
            return PublishResult("dropped", "local producer queue is full")
        except Exception as exc:
            return PublishResult("failed", f"event was not queued: {type(exc).__name__}")

    def close(self, timeout: float = 5.0) -> int:
        """Bound shutdown waiting; returned count is still undelivered."""
        return self._producer.flush(timeout)


def create_kafka_publisher(bootstrap_servers: str, topic: str) -> KafkaEventPublisher:
    """Construct the optional confluent-kafka implementation lazily."""
    from confluent_kafka import Producer

    return KafkaEventPublisher(
        Producer({"bootstrap.servers": bootstrap_servers, "enable.idempotence": True}), topic
    )
