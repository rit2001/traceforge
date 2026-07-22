"""At-least-once Kafka worker with idempotent durable processing."""

from __future__ import annotations

import json
import logging
import signal
from threading import Event
from time import monotonic
from typing import Any, Protocol

from traceforge import metrics
from traceforge.assembly import AssemblyError, AssemblyState
from traceforge.exceptions import StructuralValidationError
from traceforge.observability import message_context, shutdown, span

LOGGER = logging.getLogger("traceforge.kafka.worker")


class ConsumerLike(Protocol):
    def poll(self, timeout: float) -> Any: ...
    def commit(self, message: Any, asynchronous: bool = False) -> Any: ...
    def close(self) -> None: ...


class DlqLike(Protocol):
    def produce(self, topic: str, **kwargs: Any) -> None: ...
    def poll(self, timeout: float) -> int: ...
    def flush(self, timeout: float) -> int: ...


class KafkaAssemblyWorker:
    def __init__(
        self,
        consumer: ConsumerLike,
        dlq: DlqLike,
        state: AssemblyState,
        dlq_topic: str,
        telemetry_provider: Any = None,
    ) -> None:
        self.consumer, self.dlq, self.state, self.dlq_topic = consumer, dlq, state, dlq_topic
        self.telemetry_provider = telemetry_provider
        self.stop_event = Event()

    def _send_dlq(self, message: Any, reason: str, timeout: float = 5.0) -> bool:
        delivered: list[bool] = []

        def callback(error: Any, delivered_message: Any) -> None:
            del delivered_message
            delivered.append(error is None)

        self.dlq.produce(
            self.dlq_topic,
            key=message.key(),
            value=message.value(),
            headers=[("traceforge-error", reason[:200].encode())],
            on_delivery=callback,
        )
        deadline = monotonic() + timeout
        while not delivered and monotonic() < deadline:
            self.dlq.poll(min(0.1, max(0.0, deadline - monotonic())))
        return bool(delivered and delivered[0])

    def process_message(self, message: Any) -> bool:
        try:
            with message_context(message.headers() if hasattr(message, "headers") else None):
                with span("capture.consume"):
                    event = json.loads(message.value())
                    started = metrics.started()
                    result = self.state.process(event)
                    metrics.processed(started, result)
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            StructuralValidationError,
            AssemblyError,
        ) as exc:
            LOGGER.warning("capture event rejected", extra={"error_type": type(exc).__name__})
            if not self._send_dlq(message, type(exc).__name__):
                return False
            metrics.dlq()
        self.consumer.commit(message=message, asynchronous=False)
        return True

    def run(self, poll_timeout: float = 0.5) -> None:
        def stop(signum: int, frame: Any) -> None:
            del signum, frame
            self.stop_event.set()

        previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            while not self.stop_event.is_set():
                message = self.consumer.poll(poll_timeout)
                if message is None:
                    continue
                if message.error():
                    LOGGER.warning(
                        "Kafka consume error", extra={"error_type": type(message.error()).__name__}
                    )
                    continue
                self.process_message(message)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            self.consumer.close()
            self.state.close()
            self.dlq.flush(5.0)
            shutdown(self.telemetry_provider)
