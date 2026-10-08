# Architecture

## Current Implementation

The original spike architecture was local, narrow, and file-based. The v0.2 work preserves that replay core while adding an optional local asynchronous ingestion path. The v0.3 deployment gate schedules the same path on a local kind Kubernetes cluster without changing replay semantics. Terraform v0.4 adds local state and lifecycle management for a deliberately small Kubernetes foundation around that unchanged workload topology.

Current component status:

- **Implemented:** explicit controlled capture with best-effort redaction; Replay Capsule `0.1.0` and `0.2.0` sealing and validation; exact replay with recorded model, HTTP, and generic tool outcomes; deterministic observation comparison; separate regression evaluation; pytest export; CLI; local workbench and SQLite replay history.
- **Implemented in the optional local distributed path:** Go ingestion, bounded enqueueing, Kafka transport, Python validation/assembly, SQLite event-ID deduplication and ordering, DLQ commit safety, sealed capsule output, W3C propagation, optional spans, and Prometheus metrics.
- **Partial:** framework integration coverage. The repository has one bounded LangGraph adapter and
  framework-independent capture/dependency primitives; a separate Agentic-chatbot worktree proves
  one real application-owned adapter, not arbitrary framework capture.
- **Planned:** fork replay, fresh-model replay, richer portable event/message/dependency diff views,
  hosted trace search, and production infrastructure.

The original spike avoided services and message queues. The optional v0.2 Go/Kafka path exists specifically to keep capture publishing off the primary application's synchronous request path; it is still a local development topology, not a production deployment claim.

## Target Architecture

The next approved milestones may expand around the same replay-first core:

- Capture adapters for additional Python agent frameworks.
- A stable Replay Capsule schema with migration support.
- A local CLI and library API.
- A Python package/API that client applications can install locally.
- Richer core diff views for portable execution events, messages, dependency calls, outputs, and assertions, with framework-specific presentation derived by adapters.
- Test exporters for common Python test frameworks.
- Optional storage, indexing, or team workflows only after real usage requires them.

The target architecture still remains distinct from a generic observability product. Replay, comparison, and regression-test export remain the product center.

## Partial: Capture

Capture collects enough controlled data to seal and replay the tested examples without requiring live external dependencies. `CaptureSession` is explicit and framework-agnostic rather than magical or universal; framework adapters translate native lifecycle signals into its generic invocation, dependency, event, and observation inputs. A generic arbitrary-agent instrumentation path is not implemented.

The implemented capsule/capture path can represent:

- Initial user input and run configuration.
- Portable subject and execution-event metadata supplied by an adapter.
- Prompt and message state.
- Model request metadata and captured responses.
- Tool call names, arguments, ordering, and captured outputs.
- Ordered execution events and terminal state.
- Errors and exceptions when relevant.
- Redaction decisions or markers.

## Replay Capsule

The Replay Capsule is the boundary between capture, replay, diff, and test export. It should be portable enough for offline tests, but not treated as a production telemetry format during the spike.

The capsule may record a framework name as descriptive subject provenance, but its schema and semantics do not interpret graph, node, state-machine, or callback concepts. Framework adapters translate native concepts into the generic contract before capture.

Capsules must not require `.env` files, live API credentials, or access to the original application repository secrets.

Capsules must never contain API keys, secrets, authorization headers, or unredacted sensitive data. A sanitised capsule fixture may be stored in TraceForge for offline tests.

## Agentic-chatbot Integration Boundary

TraceForge and Agentic-chatbot remain separate repositories. The dedicated Agentic-chatbot
integration worktree installs TraceForge through its Python package/API and owns provider,
message, graph, and tool translation.

The client application is responsible for recording and exporting a sanitised Replay Capsule through that integration. TraceForge must not hard-code an absolute path to Agentic-chatbot, copy Agentic-chatbot source code, or move integration-specific end-to-end changes into the TraceForge repository.

A sanitised capsule fixture may live in TraceForge for offline tests after review. End-to-end integration changes remain in Agentic-chatbot.

## Exact Replay

Exact replay freezes both model outputs and tool outputs. It checks whether the captured execution path can be reproduced from the capsule without live services.

This is the baseline reproducibility check. If exact replay cannot reproduce the captured path, fork replay and test export are not trustworthy.

## Extension Boundaries

The feasibility implementation keeps extension points at the replay boundary rather than inside captured evidence:

- `DependencyAdapter` supplies recorded external outcomes to subject code. The current implementation consumes model, HTTP, and tool fixtures in one sequence and fails closed; future dependency kinds belong behind this interface.
- `FrameworkAdapter` invokes trusted local subject code with an injected dependency adapter. Framework-specific integrations belong here, translate native lifecycle data to generic TraceForge contracts, and must not mutate or reinterpret the capsule.
- `CapsuleStore` owns local JSON loading and saving. Future storage implementations may change retrieval but must return the immutable captured document unchanged and must not rewrite evidence during reads.

`RedactionScanner` remains the boundary for best-effort sanitization before persistence. `EventPublisher` now has direct and optional Kafka-backed consumers. Kafka carries mutable, retryable transport events; the SQLite assembler validates, orders, and deduplicates those events before the existing sealer creates evidence. Publishers and infrastructure must never modify, replace, or backfill a sealed capsule.

The replay CLI loads `MODULE:FUNCTION` runners as trusted local Python code. Importing and executing such a runner has the same authority as running that module directly; capsules must not select untrusted runner code.

Exact replay temporarily patches common Python socket entry points to fail live-network attempts. This guard is process-wide while active and is not safe for unrelated concurrent network work in other threads. It is a feasibility safeguard, not an operating-system sandbox.

Replay Capsule `0.2.0` adds generic tool dependencies to the same global sequence used by model
and HTTP calls. `CaptureSession.record_tool` executes the live callable only during capture;
`invoke_recorded_tool` accepts no live callable and returns or safely raises the recorded outcome.
Default argument sanitization rejects before execution whenever generic redaction would change
request identity. Applications may supply a reviewed deterministic sanitizer. Exact replay
reconstructs only allow-listed built-in failure types, initially `TimeoutError`, and rejects
unsupported recorded tool failures before invoking subject code. See
[ADR-0007](decisions/ADR-0007-replay-capsule-0.2-tool-dependencies.md).
For successful results, capture returns the original object and records it only when standard
scanning leaves its JSON value unchanged. Otherwise the session retains no result/dependency,
continues the application call normally, and rejects `finish()` with an unreplayable-capture error.
Generic tool capture rejects custom session scanners before tool execution so replay identity does
not depend on hidden runtime scanner configuration.

LangGraph is only the first real integration proof. Core capture, capsule, dependency, sealing,
validation, replay, regression, and future diff semantics must not import or interpret LangGraph
types, `StateGraph`, node semantics, callbacks, or graph-state rules. A future framework should add
a thin adapter and focused tests. If LangGraph's API shape appears to require a core change solely
for LangGraph, implementation stops and the adapter boundary is reconsidered. See
[ADR-0008](decisions/ADR-0008-framework-agnostic-core.md).

## Planned: Fork Replay

Fork replay is not implemented in `v0.4.1`. The intended mode freezes tool outputs while allowing model or prompt behaviour to run again. This would isolate whether a prompt, graph, or model change behaves differently against the same external facts.

The planned offline mode would use fake or recorded model adapters and recorded tool responses. It could validate replay-engine mechanics such as portable observation reconstruction, ordered event handling, tool-output injection, and diff generation.

A planned live fork experiment would use a real explicitly configured model with recorded tool outputs. It must be opt-in, may consume API quota, and must never run silently in default CI.

Live fork replay can be probabilistic because model generation may vary. Comparisons must account for that limitation and avoid overstating determinism.

## Partial: Diff

The current implementation deterministically compares captured and replay observations and exposes regression results. Richer diffing is planned at levels useful to a developer:

- Portable ordered execution events and adapter-neutral branch/transition observations.
- Tool choice and tool arguments.
- Tool outputs shown to the model.
- Model messages and final answer.
- Approved expectations and assertion results.

The first diff can be textual and structured rather than a full dashboard.

## Test Export

Test export converts developer-approved expectations into offline tests. Generated or suggested assertions are drafts until the developer approves them.

Regression promotion is the explicit developer action that creates the existing
`RegressionSpec 0.1.0` from selected expectations validated against a caller-supplied technically
completed result. The public result type is constructible and carries no provenance attestation;
Workbench independently performs exact replay with the current submitted evidence and registered
runner before promotion.
It is not a capsule transition: evidence remains immutable, while the specification remains
mutable developer-owned source. A deterministic mismatch does not block promotion of repaired
behavior. `ExecutionDiff`, `DivergenceAnalysis`, and `RegressionResult` remain derived runtime
values and are neither copied into the specification nor treated as approval. Both filesystem and
Workbench exports use the same deterministic pytest renderer; the browser receives one
content-addressed in-memory ZIP containing fixed path-safe entries and cannot choose a server path,
filename, entry name, or runner import. See
[ADR-0012](decisions/ADR-0012-regression-promotion-workflow.md).

Tests should depend on the Replay Capsule and local TraceForge code, not live model APIs, live tool APIs, application secrets, or external services.

Default unit and CI test suites must remain fully offline. Live fork experiments are evaluation runs, not default regression checks.

## Deterministic Versus Probabilistic Checks

Deterministic checks are suitable for exact replay and frozen data:

- Same captured tool output.
- Same captured model output.
- Same portable execution-event sequence under frozen responses.
- Same approved expected field or final output.

Probabilistic checks are relevant to fork replay:

- A fresh model response may differ across runs.
- Prompt changes may improve one scenario without guaranteeing broad correctness.
- A passing fork replay does not prove hallucinations are eliminated.

TraceForge should make this distinction explicit in output and documentation.

A fake model can validate replay-engine mechanics, but it cannot prove that a new prompt improves real model behaviour. Prompt-quality claims require measured live evaluation results.

## Security and Redaction Boundaries

TraceForge must treat captured traces as potentially sensitive. During the spike:

- Do not inspect or create `.env` files.
- Do not copy secrets from Agentic-chatbot or any other application.
- Do not copy Agentic-chatbot source code into TraceForge.
- Do not hard-code absolute paths to Agentic-chatbot.
- Redact sensitive request fields before storing capsules when identified.
- Exclude API keys, secrets, authorization headers, and unredacted sensitive data from capsules.
- Keep initial execution local.
- Avoid hosted upload, telemetry, or external sharing.
- Report unresolved redaction gaps before expanding scope.

## Optional Distributed Ingestion

The v0.2 local stack adds a small Go HTTP gateway and Apache Kafka after the replay feasibility loop passed. Go isolates bounded request validation and non-blocking enqueueing. Kafka decouples the primary application from Python capsule assembly. Delivery is at least once; SQLite provides durable event-id deduplication and ordered per-capture assembly, not exactly-once processing.

W3C Trace Context is propagated from HTTP into Kafka headers and extracted for one worker message at a time. Capture spans cross Go and Python services. Later replay starts a separate trace linked to operational correlation stored in SQLite, never in immutable capsule evidence. See [Local observability](observability.md).

The default core installation and ordinary dashboard image do not require Kafka or OpenTelemetry. The Compose broker/controller combination and local Collector are development-only topologies.

The implemented local flow is:

```text
Python capture SDK/client
  -> Go ingestion gateway
  -> Kafka capture-event topic
  -> Python assembly worker
  -> SQLite ordering/idempotency and correlation state
  -> sealed JSON Replay Capsule
  -> exact replay, comparison, regression evaluation, dashboard, or pytest export
```

The boundaries are intentionally asymmetric. Go owns bounded HTTP validation, readiness, backpressure, and asynchronous publishing; it does not assemble evidence or replay agents. Kafka owns retryable at-least-once transport, not evidence. Python owns event semantics, assembly, sealing, replay, and regression. SQLite owns local operational state but never becomes part of capsule integrity. The Collector observes local execution and may fail independently without invalidating capsules or replay.

## Local Kubernetes Deployment

The approved v0.3 deployment under `deploy/kubernetes` uses native manifests with a Kustomize base and a kind/local overlay. It runs the existing Go gateway image, shared Python worker/API image, Apache Kafka development broker, and OpenTelemetry Collector. Kubernetes adds local scheduling, restart, service discovery, ConfigMap injection, probes, resource constraints, security contexts, and PVC attachment around the existing containers. It does not introduce another implementation of any service or change event, capsule, replay, or telemetry semantics.

Only in-cluster communication endpoints have Services: the gateway, Kafka, API, and Collector OTLP receiver. Host access uses explicit loopback `kubectl port-forward`; there is no LoadBalancer, Ingress, authentication, or TLS. Kafka and the Collector remain labelled local-development infrastructure.

The single kind `ReadWriteOnce` claim holds worker assembly SQLite, sealed capsules, API replay history, and the Collector's bounded trace file in separate paths. The worker is fixed at one replica with `Recreate` strategy. SQLite remains a single-writer local operational store, not a distributed database. Kafka storage is ephemeral for this gate. See [ADR-0005](decisions/ADR-0005-local-kubernetes-kind-deployment.md) and the [Kubernetes runbook](operations/kubernetes.md).

## Postponed Infrastructure

ClickHouse is postponed because the product is not yet a large-scale observability database. Local Replay Capsules and offline tests should prove value before analytical storage is considered.

### Terraform/Kustomize Ownership

The v0.4 Terraform module owns the `traceforge` Namespace, its ResourceQuota and LimitRange, five dedicated ServiceAccounts, and foundation labels. Each ServiceAccount disables token automount because no workload calls the Kubernetes API. Kustomize continues to own Deployments, the Kafka StatefulSet, Services, ConfigMaps, the application PVC, and all Pod configuration. The ordinary `kind` overlay supplies an equivalent Kustomize foundation; the `terraform-kind` overlay omits it. Both overlays consume the same base and local component, so workload definitions are not duplicated and no live object is jointly managed.

The kind environment uses explicit kubeconfig path and context inputs, a pinned official Kubernetes provider, a committed dependency lock, and ignored local state. Production state would require a protected remote backend with encryption, locking, access control, backup, and tested recovery. Terraform does not create kind, images, cloud resources, secrets, or application data. See [ADR-0006](decisions/ADR-0006-terraform-kustomize-ownership.md) and the [Terraform runbook](operations/terraform.md).

Cloud Kubernetes, SaaS authentication, and payments remain postponed. The local kind and Terraform gates do not support production deployment, scale, high-availability, durability, cloud, or security claims.

## Layering and Future Placement

Immutable captured evidence belongs to the capsule/domain layer. Validation, sealing, replay, comparison, regression evaluation, and the future core diff model may read only framework-neutral contracts and must never repair or rewrite evidence. Framework-specific views are adapter-side derivations. Future repair strategies may produce proposals or new derived artifacts only.

The CLI and FastAPI dashboard are application interfaces over the same domain functions. Authentication belongs in API middleware. SQLite implements replay-history summaries plus local Kafka idempotency, assembly, and trace-correlation state without storing telemetry in or modifying capsule evidence; future databases belong behind storage interfaces. Kafka implements the optional `EventPublisher` transport boundary. Framework support belongs in optional adapters/plugins. Kubernetes and the bounded Terraform foundation remain deployment concerns and cannot change replay semantics.

See the responsibility-level [codebase map](codebase-map.md), operational [Kafka runbook](operations/kafka.md), and [observability runbook](operations/observability.md).

## Open Questions

- Which application-owned deterministic sanitizer is appropriate for the first real LangGraph tool arguments?
- Which thin LangGraph adapter seam can prove one real application without changing core semantics or implying arbitrary-agent compatibility?
- How should a future fork replay identify probabilistic fresh-model execution in results and regression policy?
- Which execution-event, message, dependency, and output differences are portable enough for the framework-neutral core diff model?
- What pipeline reliability evidence is required before expanding the local single-broker, single-worker topology?
