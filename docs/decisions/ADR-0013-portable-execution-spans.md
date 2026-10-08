# ADR-0013: Portable Execution Spans

- Status: Accepted
- Date: 2026-10-08

## Context

Replay Capsules record ordered dependencies, portable events, terminal observations, and their
integrity. They do not record which logical execution boundary contained a dependency or event, or
which recorded boundary contained another boundary. Operational OpenTelemetry correlation exists
for local service diagnosis, but those identifiers are optional process telemetry stored outside
the capsule. They are neither sanitized subject evidence nor covered by capsule integrity.

TraceForge needs the smallest portable evidence contract that can answer structural attribution
questions without implying why an outcome occurred. This decision does not introduce root-cause
inference, causal ranking, arbitrary graph edges, framework-native node semantics, or replay-side
structure comparison.

## Decision

### Replay Capsule 0.3.0

Replay Capsule `0.3.0` adds one required top-level `execution_spans` array. Versions `0.1.0` and
`0.2.0` are immutable published contracts and remain accepted without reinterpretation. A new
version is required because adding a top-level evidence domain and new required dependency/event
fields changes which documents are valid and what the sealed digest protects.

Each portable execution span has exactly these fields:

```json
{
  "execution_span_id": "weather-agent",
  "parent_execution_span_id": null,
  "sequence": 1,
  "kind": "agent",
  "name": "weather_agent",
  "component": "weather-agent"
}
```

- `execution_span_id` is a caller-supplied stable identifier using the capsule identifier grammar.
  The explicit prefix distinguishes sealed evidence from operational OpenTelemetry/W3C `span_id`
  values and aligns the span record with dependency/event attribution.
- `parent_execution_span_id` is either `null` for the one root or the identifier of the recorded
  boundary beneath which the child is structurally nested.
- `sequence` is contiguous one-based producer record order. It is deterministic structure order,
  not causal chronology.
- `kind` is an application-owned portable classification such as `agent` or `step`.
- `name` is a logical boundary name.
- `component` is an application-owned component label.

The three labels must contain a non-whitespace character, are limited to 256 Unicode characters,
and reject control characters. Unicode, quotes, path-like text, and HTML-like text remain ordinary
untrusted JSON strings; consumers must render them as text, never trusted markup.

The contract deliberately has no metadata or arbitrary relationship bag. All values are JSON and
the schema remains closed with `additionalProperties: false`.

### Parent and ordering semantics

Version 0.3 describes exactly one rooted tree, not a forest or a general graph. The first span is
the sole root, has sequence `1`, and has `parent_execution_span_id: null`. Every later span has exactly one
parent whose record appears earlier and whose sequence is lower. Span IDs are unique, sequences
are unique and contiguous, parents resolve, self-parenting is invalid, and cycles are invalid.

A structural parent means only:

> The child execution boundary was recorded as structurally nested beneath this parent boundary.

It does not mean the parent called, caused, owns, verified, controlled, or is responsible for the
child, and it does not identify a root cause. The tree is observed/developer-instrumented
structure, not control-flow or causal proof.

A rooted tree is the deliberately bounded structure contract for one capsule. It represents nested
components, fan-out, concurrent siblings, and an orchestrator with agent children without requiring
those children to run on one Python call stack. Multiple independent roots belong in separate
capsules for 0.3. Multiple-parent, hand-off, verifier, message-provenance, and causal links are
different relationship types that may be layered later; structural parentage must not be
reinterpreted to carry them.

### Dependency and event attribution

Every dependency and portable event in a 0.3 capsule has a required `execution_span_id`. The value
must resolve to an entry in `execution_spans`. Association is explicit evidence and is never
inferred from timestamps, array positions, names, or dependency/event ordering.

Attribution is required rather than optional because the purpose of 0.3 is trustworthy structural
attribution. A producer that cannot provide complete attribution must emit a 0.1 or 0.2 capsule;
it must not claim partial 0.3 evidence. Unknown associations fail validation closed.

The truthful claim is that a dependency call or event was recorded inside a named execution span.
TraceForge cannot claim that the span caused the call, event, terminal result, or later divergence.

### Capture API

`CaptureSession.execution_span(execution_span_id, *, kind, name, component)` is a synchronous context
manager available for 0.3 capture sessions. IDs are caller-provided so application instrumentation
can choose stable portable identities; TraceForge does not derive them from runtime telemetry.
Entering a span appends it in deterministic entry order and derives its parent from the session's
current stack. Dependencies and events recorded inside the context automatically receive the
current `execution_span_id`.

`kind`, `name`, and `component` are stable labels, not payload fields. Capture rejects them if the
configured scanner would transform them; it does not persist a redacted label whose identity may
have changed.

Version 0.3 rejects dependencies or events recorded without an active span, duplicate or invalid
span IDs, and finishing while a span remains active. Context exit restores the previous span even
when application code raises. The stack is owned by the `CaptureSession`; there is no hidden
process-global state and no `ContextVar`. It is the first synchronous producer implementation, not
a constraint on the sealed tree schema. One active stack is owned by one thread/task context;
attempts to use it from another thread or async task fail explicitly. The API does not promise
implicit propagation or concurrent instrumentation. A session cannot open a second root after the
first closes, and identifiers cannot be reused.

### Operational OpenTelemetry separation

Operational OpenTelemetry spans remain service/process observability: they measure and correlate
gateway, Kafka, assembly, replay, or request work and may be absent. Their trace and span IDs may
be stored in SQLite read models, but they are not copied into Replay Capsule evidence.

Portable execution spans describe sanitized subject execution structure, are framework-neutral,
are sealed with the capsule, and are deterministically validated. Similar terminology does not
make the two identity domains interchangeable. No code derives a portable `execution_span_id` from
an OTel context, falls back between the identity domains, requires them to be equal, or treats an
OTel relationship as evidence.

### Distributed capture-event evolution

Capture-event `0.2.0` remains unchanged. Capture-event `0.3.0` adds the
`execution_span_recorded` event type. A 0.3 sealed capsule is transported as:

1. `capture_started` containing the non-repeating capsule fields;
2. one `execution_span_recorded` event per span in span sequence order;
3. ordered `dependency_recorded` events carrying their required attribution;
4. ordered `observation_recorded` events carrying their required attribution; and
5. one terminal `capture_completed` event.

These transport events are derived from an already sealed capsule; they are not emitted live on
span entry or exit. Capture-event sequence is reconstruction/transport order, not causal chronology.
The parent record is guaranteed to precede its child by capsule validation before conversion.

Transport events use explicit version dispatch. The ingest gateway accepts both immutable 0.2
events and new 0.3 events. Assembly retains its existing per-capture total ordering,
content-identical idempotency, and fail-closed sequence checks, reconstructs `execution_spans`, and
then uses normal capsule sealing and validation. It neither invents missing spans nor repairs bad
associations.

### Replay behavior

Issue #6 records and validates historical portable execution structure only. Exact replay
continues to freeze and match the existing ordered dependency fixtures. The subject runner is not
required to reproduce historical span IDs or emit a current replay tree. Historical event
attribution is excluded from the current observation equality projection because there is no
replay-side span contract to compare it with.

Only the schema-level attribution member of each historical event is projected out. Application
payload members named `execution_span_id`, including nested members, remain ordinary semantic data
and are compared. Projection uses detached copies and does not mutate the capsule or ReplayResult
inputs.

`ReplayResult` remains derived runtime data and does not turn historical structure into replay
provenance. Replay validation still fails closed if a 0.3 capsule has invalid structure or
associations. Capturing and comparing replay-side spans is deferred until a separate versioned
contract can justify its semantics without creating a second replay engine.

### ExecutionDiff and DivergenceAnalysis

`ExecutionDiff 0.1.0` remains unchanged. Its four domains continue to be execution,
dependencies, events, and terminal, with no cross-domain global ordering. Portable span records
and `execution_span_id` attribution are not added silently to its comparison projections.

`DivergenceAnalysis 0.1.0` also remains unchanged. It continues to reject global chronology,
root-cause claims, and cross-domain causality. Future explicitly versioned derived views may report
that a changed dependency was recorded inside a span, but that would be execution attribution,
not evidence that the span caused the change.

### Framework neutrality

The core contract names generic logical execution boundaries only. It has no LangGraph node,
LangChain runnable, CrewAI agent, AutoGen conversation, verifier, or framework-native graph/message
type. Application code and future adapters may translate their own concepts into the five fixed
portable span fields. Adding another framework therefore requires instrumentation or a thin
adapter, not a change to capsule, replay, diff, or divergence semantics.

## Consequences

- A sealed 0.3 capsule can answer which portable span contained a dependency/event and which
  structural parent contained that span.
- Mutation of a span or attribution changes the whole-capsule digest and fails integrity
  verification.
- Producers must instrument one complete rooted tree to claim 0.3 evidence.
- The smallest valid 0.3 capsule has one root, zero dependencies, zero portable events, and a valid
  terminal observation. Spans may contain no dependency/event. Terminal status, output, and error
  remain observation-level evidence and have no span attribution in 0.3.
- Existing 0.1/0.2 capsules, capture APIs, replay results, diffs, and analyses retain their prior
  behavior.
- Workbench tree rendering is optional presentation work; the evidence contract does not depend on
  it and Issue #6 need not add a graph UI.
- TraceForge still cannot identify a root cause, rank causal responsibility, establish a global
  first divergence, or treat structural parenthood as causality.

## Alternatives Rejected

### Reuse OpenTelemetry trace/span IDs

Rejected. Operational telemetry may be absent, has different ownership and retention, and is not
sanitized sealed subject evidence.

Using the short field names `span_id` and `parent_span_id` for portable evidence was also rejected.
Although compact, they collide with existing operational field names in logs and SQLite, make grep
results ambiguous, and invite adapter authors to copy W3C identifiers. The longer evidence names
are safer at the schema boundary.

### Add fields to Replay Capsule 0.2.0

Rejected. The closed published contract is immutable, and changing it would make old validation
meaning depend on installed software version.

### Allow a forest

Rejected for 0.3. A single explicit root gives every attributed record one unambiguous structural
containment path. Independent executions should be separate capsules until a real use case
justifies forest semantics.

### Make attribution optional

Rejected. Partial attribution would let a producer claim the 0.3 structural contract while leaving
the core question unanswered. Older schema versions remain the migration path.

### Infer parents or attribution from timing/order

Rejected. Coincidence and containment are different claims, clocks are not a trusted causal
source, and inference would weaken the evidence boundary.

### Compare replay spans in ExecutionDiff 0.1.0

Rejected for this milestone. No replay-side capture contract exists yet, and silently expanding a
published derived contract would conflate historical evidence with current execution structure.
