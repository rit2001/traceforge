# TraceForge Project Memory

Read this file before architectural or implementation work. It is the durable repository-level memory and navigation entry point, not a replacement for the linked authoritative detail documents.

## Product Identity and Purpose

TraceForge is an experimental, local-first developer tool for turning a failed Python agent run into immutable Replay Capsule evidence, reproducing it offline with frozen dependencies, comparing observations, and exporting developer-approved regression tests. It is replay-first rather than a generic observability platform. Product intent belongs in [docs/product.md](docs/product.md).

## Current Verified Capabilities

- Replay Capsule v0 (`0.1.0`) structural and semantic validation, RFC 8785 canonicalization, SHA-256 request fingerprints, and sealing.
- Best-effort capture/redaction for Python plus a controlled optional LangGraph adapter.
- Exact offline replay with recorded model and HTTP outcomes, sequential request matching, fail-closed fixtures, a process-wide network guard, deterministic comparison, regression evaluation, and pytest export.
- Controlled weather, RAG citation-grounding, and tool-argument-safety examples.
- Local FastAPI dashboard with allow-listed runners and SQLite replay history.
- Optional local distributed ingestion: Go HTTP gateway, bounded asynchronous Kafka publishing, at-least-once Python consumption, SQLite ordering/idempotency, DLQ handling, capsule assembly, and sealing.
- Optional local Prometheus metrics and OpenTelemetry capture traces with later linked replay traces.

Only the executed evidence in [docs/verification-ledger.md](docs/verification-ledger.md) may be cited as verification.

## Explicit Non-Capabilities

TraceForge does not currently provide fork replay, live replay, production capture integration, broad framework support, hosted storage, authentication, multi-tenancy, production operations, automatic repair, Kubernetes, Terraform, ClickHouse, SaaS billing, or a production security guarantee. It makes no adoption, scale, benchmark, reliability, or hallucination-elimination claim.

## Architectural Invariants

- Python, LangGraph, and tool-calling agents are the first supported product boundary.
- Initial execution and default tests are local and offline.
- Replay, evidence integrity, and approved regression export remain the product center.
- Core imports do not require optional framework, dashboard, Kafka, or telemetry dependencies.
- Transport, storage, framework, and UI adapters may surround the replay domain but may not alter replay semantics.
- TraceForge and Agentic-chatbot remain separate repositories; integration code and secrets stay with the client repository.
- Significant cross-cutting or hard-to-reverse changes require an ADR before implementation.

Architecture detail belongs in [docs/architecture.md](docs/architecture.md), and the current component inventory belongs in [docs/codebase-map.md](docs/codebase-map.md).

## Immutable Evidence Rules

- Capture events and Kafka records are mutable, retryable transport data; they are not evidence.
- A completed stream becomes evidence only after assembly, validation, sanitization checks, and sealing into a Replay Capsule.
- Sealed capsule content is never repaired, enriched, reordered, or rewritten. Derivations create separate artifacts.
- Capsule integrity covers the canonical document with only `integrity.digest` omitted; request fingerprints cover canonical sanitized requests.
- Regression specifications and generated tests remain separate from original evidence and require developer approval.
- Telemetry correlation, replay history, and assembly state are operational data in SQLite or telemetry systems, never capsule fields.

The normative format and integrity rules are in [docs/contracts/replay-capsule-v0.md](docs/contracts/replay-capsule-v0.md) and [ADR-0002](docs/decisions/ADR-0002-replay-capsule-v0-format.md).

## Replay Guarantees and Non-Guarantees

Exact replay validates capsule structure, semantics, fingerprints, and integrity before invoking trusted local subject code. It freezes recorded model and tool/HTTP outcomes, matches them by sequence and sanitized request identity, rejects missing/mismatched/extra fixtures, and blocks common Python socket entry points. It never falls back to a live dependency.

These guarantees apply only to captured inputs, recorded dependencies, and tested adapters. The socket guard is process-wide, not an OS sandbox. Exact replay does not prove that capture was complete, that arbitrary code is safe, or that a fresh model would behave the same. Fork replay semantics are defined, but fork replay is not implemented. A future fresh-model fork would be probabilistic and opt-in.

## Service Boundaries and Data Flow

```text
Python capture SDK/client
  -> Go ingestion gateway (bounded HTTP validation and queueing)
  -> Kafka (keyed, at-least-once transport)
  -> Python worker (consume, validate, order, deduplicate)
  -> SQLite assembly state
  -> sealed JSON Replay Capsule
  -> exact replay / regression evaluation / dashboard / pytest export
```

The Go gateway never performs replay or claim that `202 Accepted` means broker delivery. Kafka never becomes the evidence store. The Python worker owns assembly and sealing. FastAPI is a local interface over replay functions. The Collector observes the local flow but is not required to create or replay capsules. Detailed boundaries are in [docs/architecture.md](docs/architecture.md) and [docs/services/go-ingestion-gateway.md](docs/services/go-ingestion-gateway.md).

## OpenTelemetry Correlation Model

An instrumented client supplies W3C `traceparent`/`tracestate`. Go continues that context through receive, validate, and publish spans and injects it into Kafka headers. The worker attaches the message context while consuming and creates assembly/seal descendants. Later replay starts a separate trace whose `replay.execute` span may link to capture correlation retained in SQLite. Missing telemetry or correlation never blocks evidence or replay, and trace identifiers never enter the capsule. See [docs/observability.md](docs/observability.md).

## Security Boundaries

- Never access, infer, create, or modify `.env` files or expose secrets.
- Sanitize before persistence and review every fixture before sharing or committing.
- Best-effort redaction and bounded scans reduce known risks but cannot prove secret absence.
- CLI runner imports and generated tests are trusted local code with process authority.
- The dashboard is unauthenticated and local-only; the local OTLP endpoint is unencrypted and unauthenticated.
- No external or paid API call runs without explicit approval; default tests remain offline.

The canonical security model is [docs/security.md](docs/security.md); vulnerability reporting is in [SECURITY.md](SECURITY.md).

## Accepted ADRs

- [ADR-0001](docs/decisions/ADR-0001-replay-first-product.md): replay-first product scope.
- [ADR-0002](docs/decisions/ADR-0002-replay-capsule-v0-format.md): Replay Capsule v0 format, canonicalization, integrity, and fail-closed replay.
- [ADR-0003](docs/decisions/ADR-0003-capture-event-transport.md): versioned capture-event transport, ordering, idempotency, and evidence boundary.
- [ADR-0004](docs/decisions/ADR-0004-repository-memory-and-navigation.md): mandatory repository memory, authority routing, evidence ledger, and contributor update contract.

ADRs are historical records. Supersede them with a new ADR; do not silently rewrite accepted decisions.

## Current Branch, Milestone, and Limitations

- Documented branch: `feat/distributed-ingestion-v0.2`.
- Current milestone: repository memory and contributor navigation, completed on 2026-07-21 after the local distributed-ingestion and cross-service observability milestones.
- Known limitations: no fork/live replay; no production client integration; redaction is best effort; the replay network guard is process-wide; transport is at least once; local SQLite is not a distributed store; concurrent host inspection of the worker's Docker Desktop bind-mounted WAL is unsupported; the Collector topology is local development only.

Live branch, milestone, blockers, and assumptions belong in [docs/project-state.md](docs/project-state.md), not in this summary.

## Exact Next Approved Milestone

Review the verified local distributed-ingestion and observability milestone before approving Kubernetes, Terraform, or another expansion. No infrastructure expansion is approved by this memory/navigation milestone.

## Required Reading Order

1. `PROJECT_MEMORY.md`.
2. [docs/start-here.md](docs/start-here.md) for a five-minute orientation.
3. [docs/project-state.md](docs/project-state.md) for current status and the exact next task.
4. Relevant accepted ADRs under [docs/decisions/](docs/decisions/) and relevant component documents from [docs/README.md](docs/README.md).
5. [docs/codebase-map.md](docs/codebase-map.md), relevant tests, and [docs/verification-ledger.md](docs/verification-ledger.md) before changing or claiming behaviour.
6. [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for execution and review rules.

## Memory Update Rules

- Update this file only when a durable product boundary, architectural invariant, accepted ADR set, verified capability summary, service boundary, security boundary, milestone, next approved milestone, or reading contract changes.
- Update [docs/project-state.md](docs/project-state.md) first for live state and next-task changes; keep this summary synchronized.
- Move detailed design into its authoritative component document and link it here; never paste whole documents into memory.
- Update [docs/codebase-map.md](docs/codebase-map.md) when responsibilities or extension seams move.
- Add only executed evidence to [docs/verification-ledger.md](docs/verification-ledger.md), including command/method, result, environment, date, revision, and limitations.
- Add or supersede ADRs for significant decisions. Never erase historical rationale or silently strengthen historical evidence.
- Update operations runbooks when a verified new failure mode or recovery path appears.
- Preserve user changes, inspect Git state before work, and report contradictions instead of choosing a source silently.
