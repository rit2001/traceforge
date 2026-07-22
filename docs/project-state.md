# Project State

Last verified date: 2026-07-22.

## Current Phase

The replay feasibility implementation, optional local distributed-ingestion and observability v0.2 path, repository-memory milestone, local Kubernetes v0.3 gate, and local Terraform foundation v0.4 are complete.

## Current Milestone

Terraform-managed foundation for the existing dedicated local kind deployment, with Kustomize retaining workload delivery.

This foundation milestone was completed on 2026-07-22 with a real Linux ARM64 kind plan/apply/state/drift/reconciliation/destroy lifecycle and the existing application smoke. It adds no alternative application implementation, cloud infrastructure, or production-readiness claim.

## Completed Milestones

- Documentation foundation: commit `e422aa8`.
- Replay Capsule v0 contract and structural schema: accepted after adversarial review on 2026-07-19, with JSON Schema meta-validation, two positive validation cases, and ten negative validation cases passing.
- Minimal validator/sealer: implemented on 2026-07-19 with 21 focused tests passing offline.
- Exact replay vertical slice: implemented on 2026-07-19 with sequential recorded dependencies, zero-network enforcement, a controlled weather capsule, and a separate regression specification; 33 focused tests pass offline.
- Product-completion implementation: pytest export, capture/redaction SDK, optional LangGraph integration, local FastAPI/SQLite dashboard, Docker packaging, CI, and public documentation completed on 2026-07-19 with 43 tests passing. Ruff, compile, JSON, wheel, clean-install, installed CLI, generated-test, and dashboard-health checks passed; Docker build verification was skipped because the local daemon was unavailable.
- Optional Kafka ingestion: the Go gateway, at-least-once Kafka worker, idempotent SQLite assembly, DLQ boundary, host-visible local storage, and real HTTP-to-sealed-capsule replay smoke passed on 2026-07-19.
- Cross-service observability: W3C context propagation through Go, Kafka headers, and Python plus a separate linked replay trace passed on 2026-07-19. The verified run used capture trace `79cedf78786ca8f00ac6703927002fc6` and replay trace `58340b38ce71e300e33f3f2de967c277`; required spans, the Kafka parent relationship, and the replay link to SQLite correlation span `d5b190791001b831` were present, and the bounded attribute scan passed.
- Repository memory and contributor navigation: root memory, five-minute start page, component map, verification ledger, Git policy, documentation ownership, and local runbooks completed on 2026-07-21. See the verification ledger for checks executed during completion.
- Local Kubernetes v0.3: the existing Go gateway, Apache Kafka development broker, Python worker, API/dashboard, and OpenTelemetry Collector became Ready on a dedicated kind cluster. A real capture sealed and validated, exact offline replay/regression passed, duplicate delivery remained idempotent, malformed input was rejected before enqueue, cross-service capture spans and the replay link passed, an API pod was recreated, worker replacement preserved the unchanged capsule on the RWO PVC, and application UID/GID checks returned 10001. The cluster was deleted after evidence capture. See the verification ledger for exact commands and limitations.
- Terraform foundation v0.4: the official pinned Kubernetes provider created and tracked the `traceforge` Namespace, ResourceQuota, LimitRange, and five token-less dedicated ServiceAccounts. The Terraform-backed overlay delivered the unchanged workloads; the full v0.3 smoke passed. Zero drift, controlled label drift (detailed exit 2), reconciliation, a following zero-drift plan, ordered application deletion, eight-resource destroy, empty state, namespace removal, and dedicated-cluster removal were observed. See ADR-0006 and the verification ledger.

## Repository Status

Documentation, both structural schemas, the `traceforge-replay` distribution, controlled local replay artifacts, focused tests, an optional Kafka worker, and a Go ingestion gateway exist.

The documented working branch for the Terraform foundation milestone is `feat/terraform-foundation-v0.4`.

The package provides capture with best-effort redaction, sealing, validation, exact replay, deterministic comparison, regression evaluation/export, one optional LangGraph adapter, Kafka assembly commands, and a local dashboard. The optional local distributed path provides HTTP ingestion, Kafka transport, SQLite idempotency/assembly, Prometheus metrics, and opt-in OTLP tracing. Native manifests and kind overlays deploy those same containers locally. Terraform can manage only the local Kubernetes foundation. No fork replay, live replay, production capture integration, hosted service, authentication, cloud/production Kubernetes, or cloud Terraform exists.

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
- `PROJECT_MEMORY.md` is the mandatory long-term entry point; detailed status, decisions, evidence, ownership, and runbooks retain separate canonical owners under ADR-0004.
- The local Kubernetes gate uses native manifests and Kustomize, one dedicated kind cluster, no public LoadBalancer, and the persistence/security boundaries accepted in ADR-0005.
- Terraform owns only the Namespace, ResourceQuota, LimitRange, dedicated ServiceAccounts, labels, and outputs; Kustomize owns all workloads, Services, ConfigMaps, PVC/application data, and Pod configuration under ADR-0006.

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
- Concurrent host-side inspection of the worker's bind-mounted SQLite WAL is unsupported on Docker Desktop; use a service-owned reader or inspect after shutdown.
- The kind worker remains one replica and SQLite remains single writer; the local RWO PVC and ephemeral Kafka do not provide high availability or disaster recovery.

## Deliberately Postponed Technologies

Cloud Terraform, remote production state, cloud/production Kubernetes, Helm, operators, ClickHouse, production distributed storage, SaaS authentication, TLS, autoscaling, and payment systems remain postponed. Kafka, the Collector, kind, and the local Terraform environment remain development infrastructure only.

## Exact Next Approved Task

Review the verified local Terraform foundation and ownership boundary before approving a cloud environment, remote backend, production Kubernetes, production storage, or another infrastructure expansion.

## Milestone-Boundary Checklist

Update this file when:

- A milestone is completed.
- The approved next task changes.
- A blocker is resolved or a new blocker is found.
- A significant assumption becomes a decision.
- A postponed technology is reconsidered.
