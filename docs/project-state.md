# Project State

Last verified date: 2026-10-02.

## Current Phase

The replay feasibility implementation, optional local distributed-ingestion and observability v0.2 path, repository-memory milestone, local Kubernetes v0.3 gate, local Terraform foundation v0.4, and Public Beta v0.4.1 release are complete. The GitHub repository is public; `main` and `release/v0.4.1` are pushed; tag `v0.4.1` and the Experimental Beta GitHub Release are published.

## Current Milestone

`v0.5.0 — Real Agent Capture` is active. Issue #2's generic tool dependency primitive is
implemented in the working tree for human review. It adds Replay Capsule `0.2.0` without modifying
sealed `0.1.0` evidence or broadening framework support. A real LangGraph application and
structured execution diff are not part of this completed slice.

The release aligned package, CLI, Docker, CI, public documentation, license, contributor framework, artifacts, installation, localhost workbench, Kafka topic configuration, and bounded publication-safety surfaces. It did not redesign replay semantics, implement fork replay, or add production-readiness claims.

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
- Public release candidate v0.4.1: distribution/package/CLI/Docker metadata, release artifacts, public landing documentation, named offline CI jobs, clean-wheel installation, generated regression execution, localhost-only dashboard verification, and a bounded redacted all-branch Git-history audit were completed without changing schema versions or infrastructure ownership. See the release notes and verification ledger.

## Repository Status

Documentation, Replay Capsule `0.1.0` and `0.2.0` schemas, the Capture Event schema, the `traceforge-replay` distribution, controlled local replay artifacts, focused tests, an optional Kafka worker, and a Go ingestion gateway exist.

The documented release state is on `main`; retained branch `release/v0.4.1` and tag `v0.4.1` point to the verified release commit.

The published distribution remains `0.4.1`; Replay Capsule versions and Capture Event `0.2.0` are independent contracts. The working tree now supports explicit validation/replay dispatch for Replay Capsule `0.1.0` and `0.2.0`. `0.2.0` adds generic ordered tool capture/replay with reject-by-default sensitive request identity and a bounded `TimeoutError` replay mapping. The package still has only one controlled LangGraph adapter and no real-agent integration, fork replay, live replay, hosted service, authentication, cloud/production Kubernetes, or cloud Terraform.

## Confirmed Decisions

- TraceForge is replay-first, not a broad LangSmith clone.
- First support is Python, LangGraph, and tool-calling agents.
- Initial execution is local-only.
- Exact replay freezes recorded model outputs and recorded tool outputs.
- Planned offline fork replay will use recorded tool outputs with fake or recorded model adapters; it is not implemented in `v0.4.1`.
- Planned live fork experiments will be opt-in, may consume API quota, and never run in default CI silently.
- AI-generated assertions require developer approval before becoming regression tests.
- TraceForge and Agentic-chatbot remain separate repositories.
- Agentic-chatbot integration eventually happens by installing a local TraceForge Python package/API on a dedicated integration branch.
- Sanitized capsule fixtures may be stored in TraceForge only after review.
- `PROJECT_MEMORY.md` is the mandatory long-term entry point; detailed status, decisions, evidence, ownership, and runbooks retain separate canonical owners under ADR-0004.
- The local Kubernetes gate uses native manifests and Kustomize, one dedicated kind cluster, no public LoadBalancer, and the persistence/security boundaries accepted in ADR-0005.
- Terraform owns only the Namespace, ResourceQuota, LimitRange, dedicated ServiceAccounts, labels, and outputs; Kustomize owns all workloads, Services, ConfigMaps, PVC/application data, and Pod configuration under ADR-0006.
- Replay Capsule `0.1.0` remains immutable; `0.2.0` adds generic tool dependencies and explicit version dispatch under ADR-0007.
- TraceForge's capture core, capsule/dependency contracts, sealing, validation, replay, regression,
  and future core diff semantics remain framework-agnostic under ADR-0008. LangGraph is the first
  integration proof and must stay behind a thin adapter boundary.

## Current Assumptions

- The first useful capsule can be file-based and local.
- A controlled weather grounding failure is enough to test the replay loop.
- Fake-model tests are sufficient for replay-engine mechanics but not for prompt-quality claims.
- Prompt-quality claims require measured live evaluation results.

## Known Blockers and Open Questions

- The framework-neutral capture inputs exist, but the thin real-agent adapter boundary is not yet
  proven against a real application.
- A real application-level sanitizer policy and integration boundary must still be selected for the first LangGraph application.
- Tool results requiring transformation cannot become v0.5 exact-replay evidence; no generic
  application-owned result sanitizer/projection contract exists.
- Fork replay and richer graph/message/tool diff semantics are not defined in executable code.
- Sanitization remains best effort and still requires human review before fixtures are shared.
- Concurrent host-side inspection of the worker's bind-mounted SQLite WAL is unsupported on Docker Desktop; use a service-owned reader or inspect after shutdown.
- The kind worker remains one replica and SQLite remains single writer; the local RWO PVC and ephemeral Kafka do not provide high availability or disaster recovery.

## Deliberately Postponed Technologies

Cloud Terraform, remote production state, cloud/production Kubernetes, Helm, operators, ClickHouse, production distributed storage, SaaS authentication, TLS, autoscaling, and payment systems remain postponed. Kafka, the Collector, kind, and the local Terraform environment remain development infrastructure only.

## Exact Next Approved Task

After human review of Issue #2, integrate one real sanitized LangGraph tool execution through a
thin adapter into the generic boundary and prove capture → seal → exact replay → regression →
structured diff. Keep application-specific graph code, callbacks, node/state semantics, and
sanitizer ownership outside the generic core. If LangGraph's API shape appears to require a core
change solely for LangGraph, stop and reconsider the adapter boundary.

## Milestone-Boundary Checklist

Update this file when:

- A milestone is completed.
- The approved next task changes.
- A blocker is resolved or a new blocker is found.
- A significant assumption becomes a decision.
- A postponed technology is reconsidered.
