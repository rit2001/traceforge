# Replay Capsule 0.3.0 Contract

Replay Capsule `0.3.0` adds sealed, framework-neutral execution structure. It succeeds rather than
widens `0.1.0` and `0.2.0`; readers dispatch on the exact `schema_version`, and older documents
retain their original validation and replay behavior.

## Portable execution spans

Every 0.3 capsule contains a non-empty `execution_spans` array. It is one rooted tree ordered by
span entry:

```json
{
  "execution_span_id": "weather-lookup",
  "parent_execution_span_id": "weather-agent",
  "sequence": 3,
  "kind": "step",
  "name": "weather_lookup",
  "component": "weather-client"
}
```

`execution_span_id` is an application-owned stable portable identifier, not an OpenTelemetry
`span_id`.
The first record is the sole root and has a null parent. Every later parent must resolve to an
earlier record. IDs and contiguous one-based sequences are unique. Self-parenting, cycles,
additional roots, forward/unknown parents, and extra fields fail closed.

The parent proves only that the child boundary was recorded as structurally nested beneath the
parent boundary. It does not prove caller, cause, ownership, verification, responsibility, or root
cause. The schema is a rooted tree independent of the first producer's Python stack; siblings may
represent fan-out or concurrency. Other relationship types require a future separate contract.

## Dependency and event attribution

Every 0.3 dependency and portable event has a required `execution_span_id` that resolves to the
tree. Association is explicit and sealed; it is never inferred from time, position, or name.
Changing a span field or attribution without resealing invalidates the capsule digest.

Attribution supports statements such as “the weather HTTP dependency was recorded inside
`weather-lookup`.” It does not support “`weather-lookup` caused the final answer.” Producers that
cannot provide complete attribution must use an older capsule version rather than emit partial
0.3 evidence.

## Capture and replay

`CaptureSession.execution_span(execution_span_id, *, kind, name, component)` manages a session-local
synchronous nesting stack. IDs are caller supplied. Dependency and event recording uses the
current span automatically; recording outside a span or finishing with an active span fails.
Context exit restores nesting after exceptions. There is no process-global or implicit async/task
context. An active stack cannot be shared across threads or async tasks; such use fails explicitly.
This is a producer limitation, not a schema requirement. Span labels must already be safe and
stable; they are bounded, non-blank, control-free untrusted text, and capture rejects a label the
scanner would transform rather than changing its identity during persistence.

Exact replay validates 0.3 structure and attribution before executing trusted subject code, then
uses the existing ordered dependency fixtures. Historical span IDs are not requirements on the
current runner. Only the top-level event attribution field is omitted from observation comparison;
same-named application data remains semantic. `ExecutionDiff 0.1.0` and
`DivergenceAnalysis 0.1.0` do not compare or interpret
span structure; replay-side span capture/comparison needs a future explicit contract.

## Distributed transport

Capture-event `0.3.0` adds `execution_span_recorded`. Span records travel in span sequence order
after `capture_started` and before dependencies/events. The gateway dispatches 0.2 and 0.3
envelopes explicitly. Assembly rejects mixed versions, preserves total event order and
idempotency, reconstructs the span array, and relies on normal capsule validation/sealing for the
final evidence boundary. Capture-event `0.2.0` remains unchanged.

Transport events are generated from a validated sealed capsule, not emitted during live context
entry/exit. Their sequence is deterministic transport/reconstruction order, not causal chronology.

## Operational telemetry boundary

W3C/OpenTelemetry trace/span IDs remain optional service observability outside capsule evidence.
They may correlate gateway, Kafka, assembly, and replay operations in SQLite or telemetry output.
They are never reused as portable execution span IDs, no equality or fallback exists between the
domains, and missing telemetry does not weaken or invalidate a capsule.

The structural schema is
[`schemas/replay-capsule-v0.3.schema.json`](../../schemas/replay-capsule-v0.3.schema.json). The
decision rationale and rejected alternatives are in
[ADR-0013](../decisions/ADR-0013-portable-execution-spans.md).
