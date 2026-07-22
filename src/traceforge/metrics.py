"""Bounded-cardinality optional Prometheus metrics."""

from __future__ import annotations

import os
from time import monotonic
from typing import Any

try:
    from prometheus_client import Counter, Histogram, start_http_server

    CONSUMED = Counter("traceforge_worker_consumed_events_total", "Consumed events")
    DUPLICATES = Counter("traceforge_worker_duplicate_events_total", "Duplicate events")
    DLQ = Counter("traceforge_worker_dlq_events_total", "DLQ events")
    SEALED = Counter("traceforge_worker_sealed_capsules_total", "Sealed capsules")
    REPLAY = Counter("traceforge_replay_total", "Replay outcomes", ["result"])
    PROCESSING = Histogram(
        "traceforge_worker_processing_duration_seconds", "Event processing duration"
    )
except ImportError:
    CONSUMED = DUPLICATES = DLQ = SEALED = REPLAY = PROCESSING = None


def start_worker_metrics() -> None:
    port = os.environ.get("TRACEFORGE_WORKER_METRICS_PORT")
    if port and CONSUMED is not None:
        start_http_server(int(port))


def asgi_app() -> Any:
    """Return the official Prometheus ASGI app when observability is installed."""
    try:
        from prometheus_client import make_asgi_app
    except ImportError:
        return None
    return make_asgi_app()


def started() -> float:
    return monotonic()


def processed(start: float, result: Any) -> None:
    if CONSUMED is None:
        return
    CONSUMED.inc()
    PROCESSING.observe(monotonic() - start)
    if getattr(result, "duplicate", False):
        DUPLICATES.inc()
    if getattr(result, "completed", False) and not getattr(result, "duplicate", False):
        SEALED.inc()


def dlq() -> None:
    if DLQ is not None:
        DLQ.inc()


def replay(passed: bool) -> None:
    if REPLAY is not None:
        REPLAY.labels(result="success" if passed else "failure").inc()
