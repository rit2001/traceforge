# Project State

Last verified date: 2026-07-19.

## Current Phase

The contract, feasibility implementation, and experimental MVP product-completion phases are complete.

## Current Milestone

Experimental local MVP product-completion pass.

This milestone was completed on 2026-07-19.

## Completed Milestones

- Documentation foundation: commit `e422aa8`.
- Replay Capsule v0 contract and structural schema: accepted after adversarial review on 2026-07-19, with JSON Schema meta-validation, two positive validation cases, and ten negative validation cases passing.
- Minimal validator/sealer: implemented on 2026-07-19 with 21 focused tests passing offline.
- Exact replay vertical slice: implemented on 2026-07-19 with sequential recorded dependencies, zero-network enforcement, a controlled weather capsule, and a separate regression specification; 33 focused tests pass offline.
- Product-completion implementation: pytest export, capture/redaction SDK, optional LangGraph integration, local FastAPI/SQLite dashboard, Docker packaging, CI, and public documentation completed on 2026-07-19 with 43 tests passing. Ruff, compile, JSON, wheel, clean-install, installed CLI, generated-test, and dashboard-health checks passed; Docker build verification was skipped because the local daemon was unavailable.

## Repository Status

Documentation, the structural schema, the `traceforge-replay` distribution, controlled local replay artifacts, and focused tests exist.

The package provides capture with best-effort redaction, sealing, validation, exact replay, deterministic comparison, regression evaluation/export, one optional LangGraph adapter, and `seal`, `validate`, `replay`, `export-pytest`, and `serve` commands. The local dashboard stores replay summaries in SQLite. No fork replay, live replay, production capture integration, hosted service, authentication, Kafka, Kubernetes, or Terraform exists.

## Confirmed Decisions

- TraceForge is replay-first, not a broad LangSmith clone.
- First support is Python, LangGraph, and tool-calling agents.
- Initial execution is local-only.
- Exact replay freezes recorded model outputs and recorded tool outputs.
- Offline fork replay uses recorded tool outputs with fake or recorded model adapters.
- Live fork experiments are opt-in, may consume API quota, and never run in default CI silently.
- AI-generated assertions require developer approval before becoming regression tests.
- TraceForge and Agentic-chatbot remain separate repositories.
- Agentic-chatbot integration eventually happens by installing a local TraceForge Python package/API on a dedicated integration branch.
- Sanitized capsule fixtures may be stored in TraceForge only after review.

## Current Assumptions

- The first useful capsule can be file-based and local.
- A controlled weather grounding failure is enough to test the replay loop.
- Fake-model tests are sufficient for replay-engine mechanics but not for prompt-quality claims.
- Prompt-quality claims require measured live evaluation results.

## Known Blockers and Open Questions

- Capture boundary inside Agentic-chatbot is not defined.
- Sanitization review rules for capsule fixtures are not defined.
- The exact offline fake or recorded model adapter shape is not defined.
- The package/API surface for future Agentic-chatbot integration is not defined.

## Deliberately Postponed Technologies

Go, Kafka, Terraform, Kubernetes, ClickHouse, distributed storage, microservices, SaaS authentication, and payment systems are postponed until replay evidence shows they are needed.

## Exact Next Approved Task

Review the experimental MVP and approve any next milestone before further implementation.

## Milestone-Boundary Checklist

Update this file when:

- A milestone is completed.
- The approved next task changes.
- A blocker is resolved or a new blocker is found.
- A significant assumption becomes a decision.
- A postponed technology is reconsidered.
