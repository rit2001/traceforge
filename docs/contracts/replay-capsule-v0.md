# Replay Capsule v0 Contract

Replay Capsule v0 is one UTF-8 JSON document. Its schema version is exactly `0.1.0`. The capsule is a portable, local evidence record for replay feasibility; it is not a production telemetry format.

## Top-Level Structure

Every capsule contains these required top-level sections:

| Section | Purpose |
| --- | --- |
| `schema_version` | Identifies this contract as version `0.1.0`. |
| `capsule_id` | Gives the capsule a stable, non-empty identifier. |
| `capture` | Records capture provenance, including the run identifier, capture kind, and recording time. |
| `producer` | Identifies the software and version that produced the document. |
| `subject` | Identifies the captured application revision, framework, and language. |
| `invocation` | Records the operation and sanitized input that started the run. |
| `dependencies` | Records ordered external model and HTTP interactions used as replay fixtures. |
| `original_observation` | Records internal events and the terminal result observed in the original run. |
| `redaction` | Records the redaction policy, actions, and required successful scan result. |
| `integrity` | Declares canonicalization and the capsule digest. |

External recorded dependencies are distinct from internal original observations. `dependencies` contains external model or HTTP request/outcome fixtures. `original_observation.events` contains the application or agent's internal execution evidence. An internal event must not be treated as an external fixture merely because it mentions a model or HTTP call.

The capsule contains immutable evidence of the original run. Mutable regression expectations are separate artifacts and are not embedded in v0 capsules. A developer may revise an expectation without rewriting the captured evidence; AI-generated expectations require developer approval before use as regression tests.

## Replay Semantics

Exact replay freezes both recorded model outcomes and recorded HTTP outcomes. It reconstructs the original execution against those fixtures without contacting live dependencies.

Fork replay freezes recorded external tool or HTTP outcomes while allowing the model, prompt, or agent logic to run again. A future implementation may use an offline model adapter or an explicitly opted-in live model experiment, but dependency matching and injection remain governed by this capsule.

Dependency requests are matched by both their one-based `sequence` and their sanitized request identity. The identity is represented by `request_fingerprint`, computed as SHA-256 over the RFC 8785 JSON Canonicalization Scheme (JCS) canonicalization of the sanitized `request`, and encoded as `sha256:` followed by 64 lowercase hexadecimal characters. Matching only the sequence or only the fingerprint is insufficient.

An absent fixture, an unexpected request, a sequence mismatch, or a fingerprint mismatch fails closed. Replay must never fall back to a live dependency.

A replay has separate technical and behavioural results. A run may technically complete—without an execution error—yet fail a separately maintained behavioural expectation. Completion therefore does not imply behavioural correctness.

## Dependency Outcomes

Each dependency outcome is exactly one member of a tagged union:

- `returned`, with a required `response` and no `error`.
- `errored`, with a required `error` and no `response`.

Model and HTTP dependencies share normalized identifiers, ordering, operation, request, fingerprint, outcome, and duration fields. HTTP responses retain only explicitly safe normalized headers; v0 permits only `content-type`. There is no capsule field for HTTP authorization, cookies, or credentials.

## Redaction and Integrity

Redaction happens before persistence. Sanitized requests, responses, invocation inputs, events, outputs, and errors are the only values eligible to enter the JSON document. A persisted v0 capsule records the redaction policy and actions and has `scan_result` equal to `passed`. This marker is evidence that the required process reported success, not proof that secret detection was complete.

Capsule integrity is SHA-256 over the RFC 8785 JCS canonicalization of the entire capsule with only `integrity.digest` omitted. The digest is encoded as `sha256:` followed by 64 lowercase hexadecimal characters. All other `integrity` members remain in the canonicalized value.

Timestamps and durations are diagnostic metadata. Replay and comparison must not use them as exact-equality assertions.

## Validation Responsibilities

| JSON Schema structural validation | Semantic validation performed by TraceForge code |
| --- | --- |
| Required sections and fields are present. | Dependency identifiers, event identifiers, and sequences satisfy required uniqueness and ordering rules. |
| TraceForge-owned objects reject unknown properties. | A request fingerprint equals SHA-256 of the RFC 8785 canonicalized sanitized request. |
| Identifiers, integer ranges, enums, and digest string shapes are valid; timestamps carry the Draft 2020-12 `date-time` format annotation. | The validator enables and checks `date-time` format validation; the capsule digest equals SHA-256 of the required canonicalized capsule scope. |
| A dependency outcome has exactly one valid returned-or-errored shape. | Redaction occurred before persistence and no secrets, credentials, forbidden headers, or unsafe data remain. |
| Model and HTTP records have their required normalized structure, and normalized HTTP response headers are limited to `content-type`. | Replay matches both sequence and sanitized request identity, fails closed on mismatches, and performs zero live-network fallback. |
| A persisted capsule declares a passed scan and the required integrity algorithm, canonicalization, and scope. | Diagnostic timestamps and durations are excluded from exact-equality assertions, and behavioural expectations are evaluated separately from technical completion. |

JSON Schema does not enforce cross-item uniqueness, digest or fingerprint correctness, secret absence, redaction effectiveness, or zero-network behaviour.

## Explicit v0 Exclusions

Replay Capsule v0 excludes:

- Binary attachments.
- Automatic fixes.
- Embedded regression expectations.
- Credentials.
- Arbitrary environment dumps.
- Absolute local paths.
- Live fallback.
