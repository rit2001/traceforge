# Security

This is an initial security model for the local feasibility spike. It is not a production certification, compliance claim, or hosted security design.

## Trust Boundaries

- TraceForge repository: owns replay code and sanitized fixtures once implementation begins.
- Agentic-chatbot repository: owns the client application and integration-specific changes.
- Replay Capsule: crosses from the client application into TraceForge only after sanitization.
- Live model provider: used only for explicit opt-in live experiments.
- Default unit and CI tests: must remain offline and must not require credentials.

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

The feasibility spike assumes local execution, local files, offline default tests, and no hosted upload. Live model use is separate, opt-in, and outside default CI.

## Known Limitations

- Redaction rules are not implemented yet.
- The Replay Capsule schema is not defined yet.
- Safe fixture review criteria are not detailed yet.
- No production threat model exists yet.
- No claim is made that all possible sensitive values can be detected automatically.
