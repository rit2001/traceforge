# ADR-0007: Replay Capsule 0.2 Tool Dependencies

- Status: Accepted
- Date: 2026-10-01

## Context

Replay Capsule `0.1.0` records globally ordered model and HTTP dependencies but has no
framework-independent representation for arbitrary tool calls. The v0.5.0 Real Agent Capture
milestone needs one small tool boundary that can capture sanitized arguments and outcomes, seal
them as immutable evidence, and replay them without executing the live tool.

The accepted `0.1.0` contract cannot be widened in place. ADR-0002 requires a new schema version
when a change alters the set of valid documents or replay meaning. Tool argument sanitization also
needs a stricter rule than generic best-effort masking: silently removing an identity-bearing
argument could make different requests share one recorded identity.

Recorded failures add a separate control-flow risk. If capture raises `TimeoutError` but replay
raises a generic TraceForge exception, application code that catches `TimeoutError` can take a
different path. Conversely, evidence must never select an arbitrary Python class to import or
instantiate during replay.

## Decision

TraceForge adds Replay Capsule schema version `0.2.0`. Replay Capsule `0.1.0` remains unchanged,
and readers dispatch explicitly by `schema_version`. Both versions remain structurally and
semantically validated, integrity-verified, and exactly replayable. TraceForge does not rewrite or
migrate sealed `0.1.0` evidence as part of this milestone.

### Tool dependency record

`0.2.0` extends the existing single `dependencies` array with `kind: "tool"`. A tool record has
the existing common fields and this kind-specific shape:

```json
{
  "dependency_id": "dependency-2",
  "sequence": 2,
  "kind": "tool",
  "operation": "stable.logical.tool.name",
  "request": {"arguments": {}},
  "request_fingerprint": "sha256:...",
  "outcome": {
    "status": "returned",
    "response": {"result": null}
  },
  "duration_ms": 0
}
```

An errored tool outcome uses the existing error record `{type, message, data}`. Model, HTTP, and
tool dependencies share one contiguous sequence. Replay matches the next fixture by sequence,
kind, operation, and the fingerprint of the sanitized request. Missing, unexpected, reordered,
or request-mismatched calls fail closed.

### Sanitized request identity

The request fingerprint is calculated after sanitization with the existing RFC 8785 and SHA-256
rules. The default tool-argument policy rejects a dependency when generic redaction would alter
its arguments, because the core cannot know whether the altered field is authentication metadata
or part of the meaningful tool identity. Rejection happens before the live executor is invoked or
the dependency is appended.

An application may provide an explicit deterministic sanitizer that maps raw arguments to a safe,
stable JSON representation. TraceForge evaluates that sanitizer twice for the same input and
rejects unequal outputs, then applies its known-secret scanner and rejects any remaining automatic
redaction. The application remains responsible for semantic collision resistance across distinct
inputs. Platform-level keyed pseudonymization and key management are future work.

The two evaluations receive independent deep copies, and the live executor receives a separate
copy of the original arguments. This prevents ordinary in-place sanitizer mutation from changing
the caller-owned or executor-visible JSON value. The callback must nevertheless be pure with
respect to external state: TraceForge cannot sandbox closure, process, filesystem, or network side
effects, and equal outputs do not prove their absence.

### Successful tool replay

Capture executes the live tool once and always returns the original live result to the
application. A successful tool dependency is eligible for exact-replay evidence only when the
standard scanner leaves that result unchanged as a JSON semantic value. The persisted result and
the replay-visible result are then equivalent to the capture-visible value.

If scanning would transform the result, or the result cannot be represented by the supported JSON
contract, `CaptureSession` marks its pending evidence unreplayable without retaining the raw value
or appending a transformed dependency. The tool call still returns normally. A later `finish()`
attempt raises a typed TraceForge capture-evidence error before building a capsule draft. The error
contains no result value. This separates a successful live side effect from the failure to create
legal exact-replay evidence.

The invalid-evidence marker belongs to `CaptureSession`: it owns mutable pre-capsule state and the
`finish()` boundary, while invalid evidence must never enter the immutable schema. This is one
bounded marker, not a general session state machine. Sealing cannot own the decision because the
unsafe dependency must already have been omitted before a draft exists.

Alternatives rejected for this slice:

- Raising immediately after the live call would turn evidence failure into an apparent tool-call
  failure after the tool may already have produced an external side effect.
- Silently dropping the dependency could produce a misleading capsule whose execution history is
  incomplete.
- Persisting the transformed result would make capture-visible and replay-visible values differ.
- Returning the transformed result during capture would alter live application semantics.

No application-owned result-sanitizer API is added in v0.5. Defining whether such a projection is
application-visible requires a separate contract.

### Standard scanner boundary

Generic tool capture and exact replay use the standard `best-effort-v1` scanner contract. A
`CaptureSession` configured with a custom scanner cannot record generic tool dependencies and is
rejected before live tool execution. This prevents request identity and result eligibility from
depending on scanner code or configuration absent during replay. Application-owned deterministic
argument sanitizers remain supported because their safe output is part of the fingerprinted
request and the same callable is explicitly supplied on replay.

TraceForge does not claim exactly-once tool execution. Capture can perform the original side
effect, and replay cannot undo it. Trusted application code can bypass the injected boundary or
perform filesystem, subprocess, or other local side effects. The process-wide socket guard is an
additional safeguard, not an operating-system sandbox.

### Tool failure semantics

TraceForge uses an explicit safe mapping for selected built-in exception types. During capture,
the wrapper records the error and re-raises the same original exception object. During replay, it
constructs only an allow-listed built-in exception from sanitized recorded fields. `TimeoutError`
is the initial supported mapping, preserving the common `except TimeoutError` control-flow
boundary for the tested shape.

Evidence never controls an import, module lookup, or arbitrary constructor. Before subject code
runs, exact replay checks every errored tool fixture. If its type is not in the safe mapping,
replay fails closed rather than exposing a different catchable exception inside application code.
The mapping preserves the selected exception class and sanitized message, not arbitrary custom
attributes or full provider-specific exception state.

## Compatibility strategy

- The existing `schemas/replay-capsule-v0.schema.json` remains the `0.1.0` schema and is not edited.
- A separate `0.2.0` schema adds the tool union member while retaining the existing model and HTTP
  shapes.
- Schema and validator lookup dispatch by the exact `schema_version`.
- Existing sealed `0.1.0` fixtures are neither rewritten nor migrated.
- No migration helper is added because this milestone does not require one.
- Regression specifications and telemetry correlation remain outside immutable evidence.

## Alternatives considered

| Failure design | Exact control-flow fidelity | Safety | Framework independence | Developer ergonomics | Compatibility | Arbitrary import risk |
| --- | --- | --- | --- | --- | --- | --- |
| Capture original; replay generic TraceForge error | Poor for concrete `except` branches | Safe construction | High | Simple but surprising | No format conflict | None |
| Normalize capture and replay to a TraceForge taxonomy | Good after application migration | Safe construction | High | Requires changed application exception contracts | Disruptive to existing callers | None |
| Allow-listed built-in mapping | Good for explicitly tested classes and message-only forms | Fail-closed and bounded | High | Natural for supported built-ins | Additive in `0.2.0` | None |
| Postpone errored-tool replay | No false fidelity claim | Safest | High | Successful calls only | Additive | None |

### Separate tool-fixture collection

Rejected. It would split the global model/HTTP/tool ordering, duplicate consumption rules, and
still require a new capsule version.

### Replace all dependency kinds with a new generic envelope

Rejected. The current records already share the necessary envelope. Refactoring proven model and
HTTP shapes would increase migration and compatibility risk without helping this milestone.

### Generic replay-only `RecordedToolError`

Rejected. Capture and replay could follow different application branches when code catches the
original concrete exception.

### Normalize every capture and replay failure to a TraceForge taxonomy

Rejected for this milestone. It would require integrated applications to change their exception
contracts and would not preserve existing application control flow.

### Dynamically reconstruct exception classes named by evidence

Rejected. Capsule content must not select imports or arbitrary constructors, and many exceptions
cannot be faithfully or safely reconstructed from a type name and message.

### Postpone all errored-tool replay

Rejected because a narrow safe mapping can preserve one useful, testable control-flow boundary
without pretending to support arbitrary exceptions. Unsupported types still fail closed before
subject execution.

## Consequences

- `0.2.0` can represent successful and errored generic tool boundaries without LangGraph fields.
- Existing ordered replay machinery remains the enforcement point for cross-kind call order.
- Applications with sensitive identity-bearing arguments must supply a reviewed deterministic
  sanitizer or capture fails before tool execution.
- Replay preserves `TimeoutError` catch behavior for the tested one-string message form.
- A session whose tool result requires transformation cannot produce an exact-replay draft; the
  live application still receives the original successful result.
- Additional exception mappings require explicit review and focused control-flow tests.
- Generic secret absence, arbitrary side-effect isolation, arbitrary exception reconstruction,
  and exactly-once execution are not claimed.
