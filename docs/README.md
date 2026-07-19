# Documentation Index

This directory is the authoritative map for TraceForge project knowledge. Avoid duplicating facts across documents. Each decision or fact should have one canonical home, and other documents should link to it when needed.

## Canonical Documents

- [Product](product.md): product problem, target developer, user workflow, guarantees, non-guarantees, and adoption criteria.
- [Architecture](architecture.md): feasibility-spike architecture, future target architecture, replay boundaries, Agentic-chatbot integration boundary, and postponed infrastructure rationale.
- [Weather replay spike](spikes/weather-replay.md): five-session feasibility spike plan, Weather Grounding Capsule scenario, offline requirements, and go/no-go criteria.
- [Roadmap](roadmap.md): evidence-based stage gates from documentation through possible infrastructure evaluation.
- [Project state](project-state.md): current phase, current milestone, repository status, assumptions, blockers, exact next approved task, and milestone-boundary checklist.
- [Testing strategy](testing-strategy.md): future test layers, what each layer proves, and what each layer does not prove.
- [Security](security.md): initial trust boundaries, capsule data risks, redaction requirements, safe fixtures, and local-first assumptions.
- [Glossary](glossary.md): TraceForge-specific definitions for replay, tracing, testing, and security terms.
- [Replay Capsule v0 contract](contracts/replay-capsule-v0.md): normative `0.1.0` document structure, replay semantics, validation boundaries, redaction, and integrity rules.
- [ADR-0001](decisions/ADR-0001-replay-first-product.md): accepted decision to build a replay-first product instead of a broad LangSmith clone.
- [ADR-0002](decisions/ADR-0002-replay-capsule-v0-format.md): accepted Replay Capsule v0 format, canonicalization, integrity, dependency normalization, and fail-closed fixture decisions.
- [ADR-0003](decisions/ADR-0003-capture-event-transport.md): accepted asynchronous capture-event envelope, ordering, idempotency, and evidence boundary.

## Ownership Rules

- Product intent belongs in [Product](product.md).
- System design and integration boundaries belong in [Architecture](architecture.md).
- Current status and next task belong in [Project state](project-state.md).
- Stage sequencing belongs in [Roadmap](roadmap.md).
- Test-layer meaning belongs in [Testing strategy](testing-strategy.md).
- Secret handling and fixture safety belong in [Security](security.md).
- Stable terminology belongs in [Glossary](glossary.md).
- Significant cross-cutting or hard-to-reverse decisions belong in ADRs under [decisions](decisions/).

When documents drift, update the canonical owner first and then adjust references. Do not add a second competing source of truth.
