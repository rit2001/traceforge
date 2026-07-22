# Security

This is an initial security model for the local feasibility spike. It is not a production certification, compliance claim, or hosted security design.

## Trust Boundaries

- TraceForge repository: owns replay code and sanitized fixtures once implementation begins.
- Agentic-chatbot repository: owns the client application and integration-specific changes.
- Replay Capsule: crosses from the client application into TraceForge only after sanitization.
- Live model provider: used only for explicit opt-in live experiments.
- Default unit and CI tests: must remain offline and must not require credentials.
- Go gateway and Kafka: accept and transport sanitized mutable events; they do not create immutable evidence.
- Python worker and SQLite assembly state: order/deduplicate events and seal capsules; operational correlation remains outside evidence.
- FastAPI dashboard: unauthenticated local interface with allow-listed runners and size-bounded uploads.
- OpenTelemetry Collector: optional unencrypted/unauthenticated local diagnostic endpoint; it is not an evidence store or approved external export path.
- Local kind cluster: schedules the existing containers with non-root identities, dropped capabilities, RuntimeDefault seccomp, resource bounds, and local PVC storage; it is not a production security boundary or multi-tenant environment.

## Capsule Data Risks

Capsules may contain prompts, tool arguments, tool outputs, user-provided text, model responses, graph state, timestamps, and error details. Any of these can accidentally include sensitive data.

Capsules must never contain:

- API keys.
- Secrets.
- Authorization headers.
- Session tokens.
- Unredacted personal or sensitive user data.
- Unreviewed production traces.

## Mandatory Secret Removal

Before a capsule or fixture is stored in TraceForge, sensitive values must be removed or replaced with safe placeholders. Do not commit real credentials, unsanitized production traces, or data copied from `.env` files.

TraceForge work must not inspect, create, edit, or infer `.env` files.

## Header and API-Key Redaction

Authorization headers and API keys must be redacted before persistence. Redaction should apply to tool arguments, tool outputs, model metadata, logs, errors, and any serialized request or response fields.

## Prompts, Tool Arguments, Tool Outputs, and User Data

Prompts can contain private instructions or user data. Tool arguments can contain locations, identifiers, or query text. Tool outputs can contain external facts or user-related records. User data can appear in any of these fields.

Store only the fields needed for replay and comparison. Prefer placeholders for sensitive values that do not affect the replay scenario.

## Safe Fixture Requirements

A fixture is safe for TraceForge only if:

- It is sanitized.
- It contains no credentials or authorization material.
- It contains no unredacted sensitive user data.
- It can run offline.
- It does not require `.env` files.
- It is reviewed before commit.
- It is labelled as controlled local data unless genuine production provenance is explicitly documented and sanitized.

## Local-First Assumptions

The implementation assumes local execution, local files, offline default tests, and no hosted upload. The optional Go/Kafka/Collector Compose topology binds host ports to loopback and remains development-only. The kind topology exposes no LoadBalancer or Ingress and relies on explicit loopback `kubectl port-forward`. It uses ConfigMaps only for non-sensitive values and creates no fake or empty Secret objects. Live model use is separate, opt-in, unimplemented in the current replay surface, and outside default CI.

Telemetry must not contain capture payloads, dependency responses, credentials, authorization material, raw user messages, or high-cardinality identifiers in metric labels. Trace and span identifiers belong to operational telemetry/SQLite correlation, never Replay Capsules. Collector failure must not block capture, sealing, validation, or replay.

## Known Limitations

- A versioned best-effort redaction scanner is implemented, but it cannot detect every sensitive value or prove secret absence.
- Replay Capsule v0 is defined by the accepted [contract](contracts/replay-capsule-v0.md) and [structural schema](../schemas/replay-capsule-v0.schema.json).
- Safe fixture review criteria are not detailed yet.
- No production threat model exists yet.
- The local dashboard and OTLP endpoint have no authentication, and transport is not a production security design.
- kind container controls reduce privileges for this local gate but do not constitute a Kubernetes threat model, image-signing system, network policy, admission policy, or security certification.
- No claim is made that all possible sensitive values can be detected automatically.
