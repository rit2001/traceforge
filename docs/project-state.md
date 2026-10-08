# Project State

Last verified date: 2026-10-08.

## Current Phase

The replay feasibility implementation, optional local distributed-ingestion and observability v0.2 path, repository-memory milestone, local Kubernetes v0.3 gate, local Terraform foundation v0.4, and Public Beta v0.4.1 release are complete. The GitHub repository is public; `main` and `release/v0.4.1` are pushed; tag `v0.4.1` and the Experimental Beta GitHub Release are published.

## Current Milestone

`v0.5.0 — Real Agent Capture` is active. Issue #2's generic tool dependency primitive, Issue #1's
separate real Agentic-chatbot integration proof, and Issue #3's portable structured execution diff
are complete. Issue #4 adds evidence-backed divergence analysis derived from that diff without a
second comparator, global first divergence, root-cause claim, or cross-domain causal claim.
Workbench V1 Phase 1 provides an original-run catalog, explicit evidence states, read-only run
APIs, explicit original-run source health, a reproducible controlled review catalog, and the first
execution-forensics Run Detail page over existing assembly state and sealed capsules. Exact replay
collects a detached successful-consumption dependency transcript and attaches additive
`ExecutionDiff` and `DivergenceAnalysis` values to each technically successful `ReplayResult`.
Replay Capsule schemas remain unchanged, and the core remains framework-neutral.

Issue #5 adds an explicit replay-result-to-regression workflow. The public API returns the existing
`RegressionSpec 0.1.0` from a caller-supplied constructible result, selected strict-JSON
expectations, and explicit approval; it does not attest replay provenance. Workbench reruns current
submitted evidence with a startup-registered runner and returns one coherent in-memory ZIP. Neither
path requires deterministic equality or mutates capsules, diffs, analyses, or regression results.

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
- v0.5 Issue #1 real-agent proof: the separate clean Agentic-chatbot worktree installed TraceForge
  through an editable package boundary, executed real ChatGroq and Tavily calls through its
  production LangGraph route, sealed and validated ordered model → tool → model evidence, replayed
  a persisted capsule in a fresh process with both live callables replaced by sentinels, rejected
  changed model and tool requests, and passed an external regression specification. The temporary
  live capsule was reviewed but was not added to this repository.
- v0.5 Issue #2 generic tool dependencies: Replay Capsule `0.2.0` supports globally ordered generic
  tool fixtures, fail-closed request identity, safe recorded results, and bounded approved error
  reconstruction without changing `0.1.0`.
- v0.5 Issue #3 portable structured execution diff: ADR-0009's framework-neutral `ExecutionDiff`,
  conservative dependency/event alignment, detached successful-consumption transcript, and
  additive exact-replay result integration are implemented without changing either capsule schema.
- v0.5 Issue #4 evidence-backed divergence analysis: ADR-0011's immutable versioned
  `DivergenceAnalysis` copies match state, difference counts, and section-scoped first paths from
  `ExecutionDiff`; exact replay adds bounded recorded-dependency reproduction context only after
  technical success. Workbench presents the analysis before the complete structured diff while
  explicitly refusing global chronology, root-cause, and cross-domain causal claims.
- Workbench V1 Phase 1: ADR-0010 separates original runs from replay attempts, reads capture
  metadata from assembly SQLite, validates referenced sealed capsules, exposes read-only run APIs,
  distinguishes unavailable sources from valid empty catalogs, and renders a real Run
  Detail/Execution Forensics view without accepting browser paths or imports. A controlled offline
  review-data generator recreates one `0.2.0` model → tool → model catalog outside the repository.
- v0.5 Issue #5 regression promotion and CI workflow: ADR-0012 defines promotion as an explicit
  developer decision that creates the existing regression specification from selected assertions.
  The domain API validates the selection against a supplied technically completed result;
  Workbench performs exact replay again and returns a content-addressed atomic bundle without
  accepting server paths; the existing deterministic pytest export remains the offline CI artifact.

## Repository Status

Documentation, Replay Capsule `0.1.0` and `0.2.0` schemas, the Capture Event schema, the `traceforge-replay` distribution, controlled local replay artifacts, focused tests, an optional Kafka worker, and a Go ingestion gateway exist.

The documented release state is on `main`; retained branch `release/v0.4.1` and tag `v0.4.1` point to the verified release commit.

The published distribution remains `0.4.1`; Replay Capsule versions, Capture Event `0.2.0`,
derived `ExecutionDiff` format `0.1.0`, and derived `DivergenceAnalysis` format `0.1.0` are
independent contracts. The working tree supports explicit validation/replay dispatch for Replay
Capsule `0.1.0` and `0.2.0`. `0.2.0` adds generic ordered tool capture/replay with
reject-by-default sensitive request identity and a bounded `TimeoutError` replay mapping. Exact
replay additively emits a structured diff and its bounded analysis after validated execution and
complete fixture consumption. One separate real application proves the package/API seam, but
TraceForge still has no arbitrary LangGraph instrumentation, fork replay, live replay, hosted
service, authentication, cloud/production Kubernetes, or cloud Terraform.

The local Workbench can now read original captures through `--assembly-database` or the Compose
`TRACEFORGE_ASSEMBLY_PATH` configuration. It represents incomplete, missing, invalid, and verified
evidence separately and opens assembly SQLite only in read-only mode. Unconfigured, unavailable,
ready-empty, and ready-populated sources are distinct; replay-attempt history remains independent.
A trusted startup capsule root
allows a host Workbench to resolve container-local absolute references against the same persisted
capsule directory without exposing path selection to the browser.

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
  and core diff semantics remain framework-agnostic under ADR-0008. LangGraph is the first
  integration proof and must stay behind a thin adapter boundary.
- ADR-0009 defines `ExecutionDiff` as derived runtime data, keeps exact replay technical status and
  regression evaluation separate, and leaves Replay Capsule schemas unchanged.
- ADR-0010 makes the original captured run the Workbench's primary entity, keeps replay history as
  attempts only, and preserves sealed capsule files as the evidence source.
- ADR-0011 makes `DivergenceAnalysis` a versioned derivation from `ExecutionDiff`, preserves one
  first path per evidence domain, and prohibits global chronology, root-cause, and cross-domain
  causal claims from today's evidence.
- ADR-0012 keeps historical evidence distinct from mutable approved expectations. Promotion uses
  existing assertion and export semantics, requires explicit approval, and never treats
  deterministic equality, technical completion, or an old regression verdict as automatic
  acceptance. Public `ReplayResult` values remain caller-trusted rather than provenance-attested.

## Current Assumptions

- The first useful capsule can be file-based and local.
- A controlled weather grounding failure is enough to test the replay loop.
- Fake-model tests are sufficient for replay-engine mechanics but not for prompt-quality claims.
- Prompt-quality claims require measured live evaluation results.

## Known Blockers and Open Questions

- The first application-owned facade is proven for one synchronous LangGraph route, but it is not a
  universal instrumentation API or evidence of compatibility with unrelated graph shapes.
- Tool results requiring transformation cannot become v0.5 exact-replay evidence; no generic
  application-owned result sanitizer/projection contract exists.
- Fork replay and framework-specific graph/message/tool presentation are not implemented.
- Workbench run detail has no persisted replay observation, structured diff, or assertion detail;
  divergence analysis and those records remain live derived replay results. Original runs also
  have no durable runner association.
- Workbench promotion is a generation/download flow, not a persisted regression catalog. Browser
  export is one content-addressed ZIP rather than independently collision-prone files; trusted
  filesystem export remains fail-if-present unless replacement is explicitly requested.
- Current evidence domains do not share a proven chronology and carry no causal-span or verifier
  relationship, so divergence analysis cannot identify a root cause or rank one domain as globally
  earliest.
- Pre-existing follow-up technical debt outside Issue #3: `ReplayResult` observation export alias
  hardening and `RegressionResult`/`AssertionResult` expected/actual snapshot alias hardening.
- Pre-existing `RegressionSpec 0.1.0` behavior: `equals` delegates to Python `==`, including Python's
  boolean/integer equivalence. Issue #5 reuses that evaluator unchanged rather than silently
  redesigning assertion semantics.
- Sanitization remains best effort and still requires human review before fixtures are shared.
- Concurrent host-side inspection of the worker's bind-mounted SQLite WAL is unsupported on Docker Desktop; use a service-owned reader or inspect after shutdown.
- The kind worker remains one replica and SQLite remains single writer; the local RWO PVC and ephemeral Kafka do not provide high availability or disaster recovery.

## Deliberately Postponed Technologies

Cloud Terraform, remote production state, cloud/production Kubernetes, Helm, operators, ClickHouse, production distributed storage, SaaS authentication, TLS, autoscaling, and payment systems remain postponed. Kafka, the Collector, kind, and the local Terraform environment remain development infrastructure only.

## Exact Next Approved Task

Finish and adversarially review v0.5 Issue #5 regression promotion and CI workflow. Do not begin a
subsequent feature without explicit approval.

## Milestone-Boundary Checklist

Update this file when:

- A milestone is completed.
- The approved next task changes.
- A blocker is resolved or a new blocker is found.
- A significant assumption becomes a decision.
- A postponed technology is reconsidered.
