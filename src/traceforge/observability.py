"""Optional, service-configured telemetry boundaries with no-op defaults."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_LAST_REPLAY_CORRELATION: ContextVar[dict[str, str] | None] = ContextVar(
    "traceforge_last_replay_correlation", default=None
)


def configure(service_name: str) -> Any:
    """Configure OTLP only when explicitly enabled by the service environment."""
    if os.environ.get("OTEL_SDK_DISABLED", "true").lower() == "true":
        return None
    from opentelemetry import propagate, trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.propagators.composite import CompositePropagator
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    propagate.set_global_textmap(CompositePropagator([TraceContextTextMapPropagator()]))
    return provider


def shutdown(provider: Any) -> None:
    if provider is not None:
        provider.shutdown()


def _headers(values: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in values or []:
        if key.lower() in {"traceparent", "tracestate"}:
            result[key.lower()] = value.decode() if isinstance(value, bytes) else str(value)
    return result


@contextmanager
def message_context(headers: Any) -> Iterator[None]:
    try:
        from opentelemetry import context, propagate

        token = context.attach(propagate.extract(_headers(headers)))
    except ImportError:
        yield
        return
    try:
        yield
    finally:
        context.detach(token)


@contextmanager
def span(name: str) -> Iterator[Any]:
    try:
        from opentelemetry import trace
    except ImportError:
        yield None
        return
    with trace.get_tracer("traceforge").start_as_current_span(name) as current:
        yield current


def current_correlation() -> dict[str, str] | None:
    try:
        from opentelemetry import trace
    except ImportError:
        return None
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None
    return {
        "trace_id": format(context.trace_id, "032x"),
        "span_id": format(context.span_id, "016x"),
    }


@contextmanager
def replay_span(correlation: dict[str, str] | None) -> Iterator[Any]:
    try:
        from opentelemetry import trace
        from opentelemetry.context import Context
    except ImportError:
        yield None
        return
    links = []
    if correlation:
        try:
            linked = trace.SpanContext(
                trace_id=int(correlation["trace_id"], 16),
                span_id=int(correlation["span_id"], 16),
                is_remote=True,
                trace_flags=trace.TraceFlags(1),
            )
            if linked.is_valid:
                links.append(trace.Link(linked))
        except (KeyError, TypeError, ValueError):
            pass
    with trace.get_tracer("traceforge").start_as_current_span(
        "replay.execute", context=Context(), links=links
    ) as current:
        try:
            yield current
        finally:
            span_context = current.get_span_context()
            if span_context.is_valid:
                _LAST_REPLAY_CORRELATION.set(
                    {
                        "trace_id": format(span_context.trace_id, "032x"),
                        "span_id": format(span_context.span_id, "016x"),
                    }
                )


def last_replay_correlation() -> dict[str, str] | None:
    """Return the last replay span identity in this execution context."""
    return _LAST_REPLAY_CORRELATION.get()
