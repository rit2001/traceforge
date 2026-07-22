# ADR-0004: Repository Memory and Contributor Navigation

- Status: Accepted
- Date: 2026-07-21

## Context

TraceForge now spans a replay domain, controlled examples, a local dashboard, optional Go/Kafka ingestion, and optional cross-service observability. Existing documents had begun to drift: current implementation was described as future work in some entry points, executed evidence was mixed with status prose, and contributors had no single mandatory reading path.

The repository needs durable memory without copying every product, architecture, contract, security, test, or operations document into a second monolith.

## Decision

`PROJECT_MEMORY.md` is the mandatory first read before architectural or implementation work. It owns the concise long-term summary of product identity, verified capability boundaries, invariants, evidence rules, replay guarantees, service/security boundaries, accepted decisions, current milestone/next milestone, reading order, and update contract.

Detailed authority remains distributed and explicit:

- `docs/project-state.md` owns live state and the exact next approved task.
- ADRs own significant decision history and supersession.
- Normative contracts and component documents own their detailed subjects.
- `docs/codebase-map.md` owns current repository responsibilities and extension seams.
- `docs/verification-ledger.md` owns executed verification evidence and limitations.
- `docs/operations/` owns verified local-development failure triage.
- `docs/README.md` owns documentation routing and the ownership/update table.

Memory links to those owners instead of duplicating them. Historical ADRs and evidence entries are never silently rewritten; newer decisions or verification are appended or explicitly supersede older records.

## Consequences

- Contributors and AI agents have one required entry point and a bounded reading sequence.
- Status, decisions, evidence, component ownership, and runbooks have distinct canonical owners.
- Material work has an explicit documentation update contract.
- Link/path and contradiction checks become part of documentation milestone verification.
- Maintainers must keep the concise memory synchronized without turning it into a detailed duplicate.
- This decision changes repository governance only; it does not approve application behaviour, infrastructure, Kubernetes, Terraform, hosted operation, or production claims.

## Alternatives Considered

### Use Only the Documentation Index

Rejected because an index routes to documents but does not preserve a concise durable account of invariants, evidence boundaries, current milestone, and the required contributor contract.

### Put All Detail in Project Memory

Rejected because copied contracts, architecture, status, and runbooks would create competing sources of truth and accelerate drift.

### Generate Memory Automatically

Postponed. Generation would still require authority rules and semantic review, and no measured need justifies tooling for this documentation-only milestone.
