# Roadmap

TraceForge uses evidence-based stage gates. Stages advance only when the exit criteria are met, not because a deadline elapsed.

Go, Kafka, Terraform, Kubernetes, distributed storage, and microservices remain postponed until measured replay needs require them.

## Current Implementation Evidence

As of 2026-07-19, documentation and Replay Capsule v0, validation/sealing, exact offline replay, separate regression evaluation, pytest export, best-effort capture/redaction, one optional LangGraph integration, and a local FastAPI/SQLite dashboard are implemented and tested with controlled local data. Fork replay, real Agentic-chatbot integration, measured live experiments, hosted services, and production hardening are not complete.

The local dashboard is an MVP inspection surface, not evidence that Stage 7 service-infrastructure criteria are met. Docker and CI package the local product; Kafka, Kubernetes, Terraform, distributed storage, SaaS authentication, and payments remain postponed.

## Stage 0: Documentation and Feasibility Definition

Entry criteria:

- Repository exists.
- Product definition and boundaries are known.

Exit criteria:

- Core documentation exists.
- Current project state is recorded.
- Weather replay spike is defined.
- Significant initial decisions are captured in ADRs.

Non-goals:

- Source code.
- Package metadata.
- Docker or service infrastructure.
- Test fixtures.

## Stage 1: Controlled Weather Grounding Capsule

Entry criteria:

- Weather replay spike is approved.
- Agentic-chatbot integration boundary is understood.

Exit criteria:

- Controlled local weather failure is described.
- Required captured fields are defined.
- Sanitization requirements are defined.
- Acceptance criteria for a safe fixture are approved.

Non-goals:

- Live model evaluation.
- Production incident claims.
- Copying Agentic-chatbot source code.
- Accessing `.env` files.

## Stage 2: Exact Offline Replay

Entry criteria:

- Weather Grounding Capsule fields are defined.
- A sanitized fixture plan exists.

Exit criteria:

- Exact replay can reproduce the captured path using recorded model outputs and recorded tool outputs.
- Default tests remain offline.
- Replay failure modes are documented.

Non-goals:

- Prompt improvement claims.
- Live model calls.
- Hosted trace storage.

## Stage 3: Fork Replay and Execution Diff

Entry criteria:

- Exact offline replay works for the controlled capsule.
- Tool-output freezing is reliable for the scenario.

Exit criteria:

- Offline fork replay can run with recorded tool outputs and fake or recorded model adapters.
- Diff output identifies relevant path, tool, and final-answer differences.
- The docs distinguish replay mechanics from real model-quality evidence.

Non-goals:

- Automatic fixes.
- Claims that hallucinations are eliminated.
- Silent live evaluations in CI.

## Stage 4: Regression-Test Export

Entry criteria:

- Exact replay and offline fork replay are working for the controlled scenario.
- Diff output is useful enough to review.

Exit criteria:

- Developer-approved expectations can be exported as offline regression tests.
- AI-generated assertions remain drafts until approved.
- Tests make no paid API calls by default.

Non-goals:

- Benchmark suites.
- Coverage claims.
- Production reliability claims.

## Stage 5: Agentic-chatbot Integration

Entry criteria:

- Local TraceForge package/API shape is defined.
- Offline replay and test export have passed on a sanitized fixture.

Exit criteria:

- Agentic-chatbot installs TraceForge locally on a dedicated integration branch.
- Agentic-chatbot records and exports a sanitized Replay Capsule.
- End-to-end integration changes remain in Agentic-chatbot.
- TraceForge contains no hard-coded absolute path to Agentic-chatbot.

Non-goals:

- Copying Agentic-chatbot source into TraceForge.
- Committing credentials or unsanitized traces.
- General framework support beyond the approved integration.

## Stage 6: Measured Live Experiments

Entry criteria:

- Offline replay mechanics and regression-test export work.
- Live experiment approval and configuration are explicit.

Exit criteria:

- Live fork experiments use recorded tool outputs and explicitly configured models.
- API quota use is visible and opt-in.
- Prompt-quality claims are backed by measured live evaluation results.

Non-goals:

- Default CI live calls.
- Fake-model prompt-quality claims.
- Production monitoring claims.

## Stage 7: Evaluate Service Infrastructure

Entry criteria:

- Local replay workflow has demonstrated value.
- A real need exists for storage, indexing, sharing, or team workflows.

Exit criteria:

- Infrastructure requirements are written from measured needs.
- ADRs capture any hard-to-reverse technology choices.
- Simpler local options have been considered.

Non-goals:

- Adding Kafka, Kubernetes, ClickHouse, Terraform, distributed storage, or microservices by default.
- SaaS authentication or payments before a product need is demonstrated.
- Rebranding TraceForge as a generic observability dashboard.
