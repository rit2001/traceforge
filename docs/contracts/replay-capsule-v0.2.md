# Replay Capsule 0.2.0 Contract

Replay Capsule `0.2.0` is one UTF-8 JSON document. It is the successor to, not a
reinterpretation of, Replay Capsule `0.1.0`. Readers dispatch by the exact `schema_version`.
Sealed `0.1.0` evidence remains valid and is never widened, rewritten, or implicitly migrated.

The top-level structure, canonicalization, integrity scope, observation structure, redaction
record, model dependency, and HTTP dependency are unchanged from `0.1.0`. Regression
specifications and telemetry correlation remain separate from immutable evidence.

The contract remains framework-agnostic. `subject.framework` is descriptive provenance only, and
generic internal events do not acquire graph, node, state-machine, or callback semantics. A
framework adapter must translate native concepts before capture; sealing, validation, replay,
regression, and diff logic do not interpret framework-specific meaning.

## Generic tool dependency

`0.2.0` adds `tool` to the single globally ordered dependency union:

```json
{
  "dependency_id": "dependency-2",
  "sequence": 2,
  "kind": "tool",
  "operation": "catalog.lookup",
  "request": {
    "arguments": {"item_id": 1}
  },
  "request_fingerprint": "sha256:...",
  "outcome": {
    "status": "returned",
    "response": {
      "result": {"name": "safe item"}
    }
  },
  "duration_ms": 0
}
```

An errored tool outcome uses the existing tagged error form:

```json
{
  "status": "errored",
  "error": {
    "type": "TimeoutError",
    "message": "controlled timeout",
    "data": null
  }
}
```

`operation` is the stable logical tool identity. `request.arguments`, returned `result`, and error
fields contain sanitized JSON values only. Runtime callables, credentials, environment data,
telemetry correlation, retry state, and regression expectations are not capsule fields.

## Identity and ordering

The request fingerprint is SHA-256 over the RFC 8785 canonicalization of the complete sanitized
`request` object. Sanitization therefore precedes fingerprinting.

Replay matches the next dependency using the global one-based sequence, kind, operation, and
sanitized request fingerprint. Model, HTTP, and tool calls occupy the same sequence. A missing,
unexpected, reordered, operation-mismatched, or argument-mismatched call fails closed. Replay
completion fails if any recorded fixture remains unused.

## Tool argument sanitization

Generic redaction must not silently make distinct meaningful arguments share a request identity.
The default tool boundary rejects capture before executing the live tool when its best-effort
scanner would alter any argument.

An application may provide an explicit deterministic sanitizer that maps raw arguments to safe,
stable JSON. TraceForge checks repeated evaluation for the same input and rejects remaining values
that would trigger generic redaction. The application owns semantic collision resistance across
different inputs and must use the same sanitizer during capture and replay. Keyed platform-level
pseudonymization and key management are not implemented in `0.2.0`.

Each deterministic check receives an independent deep copy of the arguments; the sanitizer is
never intentionally given the caller's original mutable JSON value. The live executor receives a
separate deep copy of that original value. A sanitizer is still application code and is invoked
twice: it must be pure with respect to closure, process, filesystem, and network state. TraceForge
cannot detect side effects that happen outside the copied argument or prove determinism merely
because two returned JSON values compare equal.

## Successful and errored replay

Successful replay returns `outcome.response.result` without receiving or invoking a live tool
callable. Capture returns the original live result to the application. A returned tool dependency
may enter a capsule only when the standard scanner leaves the result unchanged under RFC 8785 JSON
canonicalization. For every accepted dependency, the capture-visible, persisted, and
replay-visible result are therefore the same JSON semantic value.

If the standard scanner would transform the result, or the result is not supported JSON, the live
call still returns normally but its `CaptureSession` becomes incapable of producing exact-replay
evidence. The raw result and transformed dependency are not retained. `finish()` fails with a
typed capture-evidence error before constructing a draft, and the error text contains no result
data. No generic result-sanitizer API exists in v0.5.

Generic tool capture is supported only on a `CaptureSession` using the standard
`best-effort-v1` scanner. A custom session scanner is rejected before tool execution, so request
identity never depends on hidden scanner configuration unavailable during replay.

For errored outcomes, evidence cannot select imports or arbitrary constructors. TraceForge
reconstructs only explicitly approved built-in exception mappings. The initial mapping is the
message-only `TimeoutError` form. Capture records the failure and re-raises the original exception;
replay raises a new `TimeoutError` with the sanitized recorded message. Unsupported recorded tool
exception types cause replay to fail before subject code executes.

This preserves the tested concrete catch boundary, not arbitrary exception attributes or
provider-specific state.

## Guarantees and limitations

- Exact replay never calls a live tool through the recorded-tool boundary.
- Exact replay makes no live-fallback attempt after mismatch or fixture exhaustion.
- Capture may execute the original side effect and does not claim exactly-once behavior.
- Trusted subject code may bypass the boundary or perform other local side effects.
- The socket guard is not an operating-system sandbox.
- Best-effort scanning and deterministic sanitizer checks do not prove universal secret absence.
- Results requiring sanitization cannot produce a Replay Capsule in this version.

The structural schema is
[`schemas/replay-capsule-v0.2.schema.json`](../../schemas/replay-capsule-v0.2.schema.json). The
decision rationale and rejected alternatives are in
[ADR-0007](../decisions/ADR-0007-replay-capsule-0.2-tool-dependencies.md).
