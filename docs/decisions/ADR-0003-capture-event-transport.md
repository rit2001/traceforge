# ADR-0003: Versioned Capture-Event Transport

- Status: Accepted
- Date: 2026-07-19

## Context

Capture must not block or crash the primary AI application. A transport envelope is needed before Kafka or another publisher can carry sanitized capture facts to an asynchronous assembler.

## Decision

TraceForge capture events use the `0.2.0` JSON envelope defined by [`schemas/capture-event-v0.schema.json`](../../schemas/capture-event-v0.schema.json). `capture_id` is the Kafka message key and ordering scope, positive `sequence` orders events within that capture, and `event_id` is the idempotency key. Payloads are sanitized before validation and enqueueing.

Kafka events are mutable, retryable transport messages. They are not evidence. Only a completed, validated event stream assembled into a Replay Capsule and passed through the existing sealer becomes immutable evidence.

Delivery is at least once. Consumers deduplicate by `event_id`; this does not create exactly-once processing. Producers report accepted, dropped, or failed enqueue outcomes and never translate an enqueue acknowledgement into a completed-capture claim.

## Consequences

- Publishing can remain asynchronous and fail soft on the application request path.
- Per-capture ordering and idempotent handling are explicit semantic responsibilities beyond JSON Schema.
- Sanitization quality remains best effort; schema validity does not prove secret absence.
- Transport evolution requires a new schema version and compatible consumer migration before publishers emit it.
