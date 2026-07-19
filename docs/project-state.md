# Project State

Last verified date: 2026-07-19.

## Current Phase

The contract phase is complete, and TraceForge is in its first feasibility implementation phase. Day 2 implementation is complete.

## Current Milestone

Exact replay vertical slice.

This milestone was completed on 2026-07-19.

## Completed Milestones

- Documentation foundation: commit `e422aa8`.
- Replay Capsule v0 contract and structural schema: accepted after adversarial review on 2026-07-19, with JSON Schema meta-validation, two positive validation cases, and ten negative validation cases passing.
- Minimal validator/sealer: implemented on 2026-07-19 with 21 focused tests passing offline.
- Exact replay vertical slice: implemented on 2026-07-19 with sequential recorded dependencies, zero-network enforcement, a controlled weather capsule, and a separate regression specification; 33 focused tests pass offline.

## Repository Status

Documentation, the structural schema, a minimal Python package, controlled local replay artifacts, and focused tests exist.

The package provides RFC 8785 canonicalization, validation, sealing, sequential recorded dependency playback, exact replay, deterministic comparison, regression evaluation, and `seal`, `validate`, and `replay` CLI commands. A controlled sealed weather capsule and regression specification exist; no live replay, production capture adapter, dashboard, Docker files, or service infrastructure exists.

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

Review the Day 2 exact replay implementation and results. No Day 3 implementation task is approved yet.

## Milestone-Boundary Checklist

Update this file when:

- A milestone is completed.
- The approved next task changes.
- A blocker is resolved or a new blocker is found.
- A significant assumption becomes a decision.
- A postponed technology is reconsidered.
