# Codebase Map

This document owns the current repository responsibility map. Update it whenever a component moves, changes ownership, gains a durable input/output, or adds an extension seam. It excludes generated caches, virtual environments, local databases, build outputs, and other ignored artifacts.

## Schemas

- **Responsibility:** Define the structural contracts for sealed Replay Capsules and transport capture events.
- **Important files:** [schemas/replay-capsule-v0.schema.json](../schemas/replay-capsule-v0.schema.json), [schemas/replay-capsule-v0.2.schema.json](../schemas/replay-capsule-v0.2.schema.json), [schemas/replay-capsule-v0.3.schema.json](../schemas/replay-capsule-v0.3.schema.json), [schemas/capture-event-v0.schema.json](../schemas/capture-event-v0.schema.json), [schemas/capture-event-v0.3.schema.json](../schemas/capture-event-v0.3.schema.json), and [schemas/fixtures/capture-events/](../schemas/fixtures/capture-events/).
- **Inputs:** UTF-8 `0.1.0`, `0.2.0`, or `0.3.0` capsule documents, or `0.2.0`/`0.3.0` capture-event envelopes.
- **Outputs:** Structural acceptance or a validation failure.
- **Invariants:** Draft 2020-12; TraceForge-owned objects reject unknown properties; schema validation does not prove semantic validity, integrity, ordering, idempotency, or secret absence; published 0.1/0.2 contracts remain immutable; framework is descriptive provenance and no schema field has LangGraph graph/node/state semantics.
- **Extension points:** A new versioned schema plus compatibility/migration rules; never reinterpret an existing version silently.
- **Tests:** [tests/test_capsule.py](../tests/test_capsule.py), [tests/test_capture_event_schema.py](../tests/test_capture_event_schema.py), [tests/test_capture_event_fixtures.py](../tests/test_capture_event_fixtures.py), and the Go validator tests.

## Core Python Capsule, Sealing, and Validation

- **Responsibility:** Canonicalize JSON, fingerprint requests, calculate capsule integrity, seal sanitized drafts, validate sealed evidence, expose precise domain errors, and load/save JSON.
- **Important files:** [canonical.py](../src/traceforge/canonical.py), [schema.py](../src/traceforge/schema.py), [sealing.py](../src/traceforge/sealing.py), [validation.py](../src/traceforge/validation.py), [store.py](../src/traceforge/store.py), [exceptions.py](../src/traceforge/exceptions.py), and [interfaces.py](../src/traceforge/interfaces.py).
- **Inputs:** Sanitized capsule drafts or sealed capsule documents.
- **Outputs:** A new sealed document, validated immutable data, or a typed failure.
- **Invariants:** Sealing does not mutate the caller's draft; validation never repairs; fingerprints and integrity use RFC 8785 plus SHA-256; unsupported versions fail; derived fields are recalculated by the sealer; 0.3 has one root, unique contiguous span order, earlier resolving parents, and required dependency/event associations; structural parents never imply causality; core validation and sealing never interpret framework-native types or lifecycle semantics.
- **Extension points:** `CapsuleStore` for retrieval, version-dispatched schemas/migrations, and explicitly versioned dependency kinds.
- **Tests:** [tests/test_capsule.py](../tests/test_capsule.py) and [tests/test_cli.py](../tests/test_cli.py).

## Replay, Structured Diff, Divergence Analysis, Regression, and Promotion

- **Responsibility:** Supply recorded dependencies, retain a detached successful-consumption runtime transcript, block live network access, invoke trusted local runners, compare portable executions, derive bounded evidence-domain findings, evaluate a separate approved specification, explicitly promote selected reviewed expectations, and export pytest.
- **Important files:** [dependencies.py](../src/traceforge/dependencies.py), [network.py](../src/traceforge/network.py), [diff.py](../src/traceforge/diff.py), [divergence.py](../src/traceforge/divergence.py), [replay.py](../src/traceforge/replay.py), [regression.py](../src/traceforge/regression.py), [promotion.py](../src/traceforge/promotion.py), and [export.py](../src/traceforge/export.py).
- **Inputs:** A valid sealed capsule, trusted `FrameworkAdapter`/runner, and optional regression specification. `compare_execution()` consumes portable original/replay observations plus ordered recorded/runtime dependency streams. `analyze_divergence()` consumes only a completed `ExecutionDiff` plus bounded exact-replay completion context. `promote_regression()` consumes a caller-supplied completed `ReplayResult`, explicit existing-contract strict-JSON assertions, and explicit approval; the public value does not attest provenance.
- **Outputs:** `ReplayResult` with additive `ExecutionDiff` and `DivergenceAnalysis` values after successful exact replay, standalone derived values, assertion results, a detached `RegressionSpec 0.1.0`, generated offline pytest source/file, or a deterministic coherent regression ZIP.
- **Invariants:** Exact replay freezes model, HTTP, and generic tool outcomes; requests match one global sequence and sanitized identity; missing/mismatched/reordered/extra dependencies fail closed; no live fallback; unsupported tool failures stop before subject execution; complete fixture consumption precedes diff and analysis construction; 0.3 portable spans remain historical evidence and are not runner obligations or inputs to `ExecutionDiff 0.1.0`; evidence remains unchanged; assertions live outside the capsule; promotion requires a supplied technically completed result and literal developer approval, selects no fields automatically, rejects non-JSON values and exact duplicates, permits deterministic mismatch and a missing/failed prior regression, and never changes evidence or derived results; runtime transcript, diff, and analysis are derived runtime data and are not persisted automatically; analysis copies section summaries and first paths without recomparison; it never claims global chronology, root cause, or cross-domain causality; replay, regression, diff, analysis, and promotion semantics operate only on framework-neutral observations.
- **Extension points:** `DependencyAdapter`, thin `FrameworkAdapter` implementations, framework-neutral `compare_execution()` inputs, additive evidence locations under a later versioned contract, adapter-side framework-specific presentations, and future explicitly approved fork replay. A new framework must not require evidence/replay/diff/analysis semantic changes.
- **Tests:** [tests/test_execution_diff.py](../tests/test_execution_diff.py), [tests/test_tool_dependencies.py](../tests/test_tool_dependencies.py), [tests/test_replay.py](../tests/test_replay.py), [tests/test_promotion.py](../tests/test_promotion.py), [tests/test_export.py](../tests/test_export.py), [tests/test_case_studies.py](../tests/test_case_studies.py), and [tests/test_langgraph_integration.py](../tests/test_langgraph_integration.py).

## Capture SDK

- **Responsibility:** Record invocation facts, portable execution boundaries, dependency outcomes, execution events, and observations while applying best-effort sanitization before returning a draft.
- **Important files:** [capture.py](../src/traceforge/capture.py), [capture_events.py](../src/traceforge/capture_events.py), [interfaces.py](../src/traceforge/interfaces.py), and [integrations/](../src/traceforge/integrations/).
- **Inputs:** Local Python invocation data, explicit 0.3 `execution_span()` contexts, model/HTTP requests, tool arguments and callables, dependency outcomes, events, an optional scanner, and an optional deterministic tool-argument sanitizer.
- **Outputs:** Sanitized unsealed capsule drafts, a typed unreplayable-capture failure at `finish()`, or sanitized validated transport events.
- **Invariants:** Secrets are never intentionally persisted; tool arguments fail before execution when generic redaction would change identity; successful live tool results are returned unchanged and enter evidence only when standard scanning preserves their JSON value; invalid tool-result evidence is not retained; 0.3 `execution_span_id` values are caller-owned and nesting is session-local and synchronous with automatic current-span attribution; one active stack belongs to one thread/task context and cross-context use fails; this producer stack does not constrain the durable tree schema; missing/duplicate/invalid IDs and unbalanced capture fail closed; no operational trace ID is reused; scan success is not proof of safety; derived fingerprints/integrity are absent until sealing; capture core has no LangGraph imports, types, node semantics, callbacks, or framework-specific assumptions.
- **Extension points:** `RedactionScanner`, thin framework adapters that translate native signals into generic capture inputs, dependency wrappers, and `EventPublisher`. The first real external proof is application-owned in the separate Agentic-chatbot worktree and consumes only public package APIs. If an integration needs a core change solely due to its API shape, stop and reconsider the adapter boundary.
- **Tests:** [tests/test_capture.py](../tests/test_capture.py), [tests/test_tool_dependencies.py](../tests/test_tool_dependencies.py), [tests/test_langgraph_integration.py](../tests/test_langgraph_integration.py), and capture-event tests.

## Kafka Publisher

- **Responsibility:** Validate and sanitize capture events, enqueue asynchronously with `capture_id` as the key, report accepted/dropped/failed enqueue outcomes, and bound shutdown.
- **Important files:** [kafka.py](../src/traceforge/kafka.py) for the Python publisher and [publisher.go](../services/ingest-gateway/internal/publisher/publisher.go) for the Go publisher.
- **Inputs:** Versioned capture events and broker configuration.
- **Outputs:** Kafka records on `traceforge.capture.v1`, delivery counters/callbacks, or backpressure/unavailable status.
- **Invariants:** No per-request flush; enqueue acceptance is not broker delivery or capsule completion; delivery is at least once; the key is the ordering scope; payloads are not evidence; capture-event 0.2 and 0.3 dispatch explicitly.
- **Extension points:** `EventPublisher`, bounded producer configuration, and version-compatible transport implementations.
- **Tests:** [tests/test_kafka_publisher.py](../tests/test_kafka_publisher.py) and [publisher_test.go](../services/ingest-gateway/internal/publisher/publisher_test.go).

## Assembly State

- **Responsibility:** Persist event IDs and per-capture sequence state, reject gaps/conflicts, deduplicate redelivery, assemble completed streams, seal capsules, and retain optional trace correlation.
- **Important files:** [assembly.py](../src/traceforge/assembly.py) and [store.py](../src/traceforge/store.py).
- **Inputs:** Sanitized ordered capture events.
- **Outputs:** Durable SQLite state and one sealed JSON capsule per completed `capture_id`.
- **Invariants:** `event_id` deduplication is idempotent handling, not exactly-once transport; sequence is contiguous per capture; mixed event versions fail; 0.3 span records are reconstructed before normal sealing; a completed capture cannot reopen; operational trace correlation stays outside evidence.
- **Extension points:** `AssemblyState` and future storage implementations that preserve atomic ordering, deduplication, and evidence rules.
- **Tests:** [tests/test_assembly.py](../tests/test_assembly.py) and [tests/test_observability.py](../tests/test_observability.py).

## Worker

- **Responsibility:** Poll Kafka, attach W3C message context, process through assembly state, publish poison messages to the DLQ, and commit only after durable processing or confirmed DLQ delivery.
- **Important files:** [kafka_worker.py](../src/traceforge/kafka_worker.py), [kafka_runtime.py](../src/traceforge/kafka_runtime.py), and worker wiring in [cli.py](../src/traceforge/cli.py).
- **Inputs:** Records from `traceforge.capture.v1` and runtime paths/configuration.
- **Outputs:** SQLite assembly changes, sealed capsules, `traceforge.capture.dlq.v1` records, metrics, and capture spans.
- **Invariants:** Manual commits; no commit before persistence; no commit when DLQ confirmation fails; one message context is attached only for its processing scope; shutdown closes consumer/state and bounds DLQ flush.
- **Extension points:** `ConsumerLike`, `DlqLike`, `AssemblyState`, telemetry provider, and operational configuration.
- **Tests:** [tests/test_assembly.py](../tests/test_assembly.py) and [tests/test_observability.py](../tests/test_observability.py).

## FastAPI and Dashboard

- **Responsibility:** Provide a read-only original-run catalog with explicit source health, forensics view, local health endpoint, responsive evidence/replay workbench, compact evidence-backed divergence presentation, explicit regression-promotion/download flow, JSON replay API, startup-only registered runners, packaged built-in examples, metrics mount, append-only replay-attempt summaries, and reproducible controlled review data.
- **Important files:** [workbench.py](../src/traceforge/workbench.py), [web.py](../src/traceforge/web.py), [history.py](../src/traceforge/history.py), [templates/dashboard.html](../src/traceforge/templates/dashboard.html), [static/dashboard.css](../src/traceforge/static/dashboard.css), and [create_workbench_review_data.py](../scripts/create_workbench_review_data.py).
- **Inputs:** Read-only assembly SQLite metadata, its trusted capsule references, an optional trusted startup capsule root for cross-environment resolution, size-bounded JSON capsule and optional existing specification selected as one explicit example/upload/paste mode, and a runner ID registered at server startup.
- **Outputs:** Immutable `RunCatalogSnapshot`/`RunSummary`/`RunDetail` values, `GET /api/run-source`, `GET /api/runs`, `GET /api/runs/{run_id}`, execution-forensics HTML, JSON replay/diff/analysis/regression results, one content-addressed promoted-regression ZIP, local SQLite replay-attempt summaries, and optional generated review data outside the repository.
- **Invariants:** Original-run SQLite opens in read-only mode and never creates a missing configured source; unconfigured, unavailable, ready-empty, and ready-populated states remain distinct; original runs come only from assembly state; replay history stores attempts only; sealed files remain evidence; missing/invalid evidence is explicit and never replayable; recorded paths take precedence and relocation fallback is confined to `<trusted root>/<capture_id>.json`; traversal and symlink escape are rejected; API responses never expose configured paths; browser input cannot select paths, roots, imports, output names, archive entries, or overwrite controls; custom `ID=MODULE:FUNCTION` registrations are trusted local startup configuration only; uploads are bounded; promotion reruns the current capsule with that registered runner, starts with no selected assertions, requires explicit confirmation, and returns one in-memory atomic bundle; built-in examples have fixed reviewed paths; frontend code renders rather than computes replay/diff/analysis/regression/promotion semantics; analysis precedes full diff detail but does not rank domains or infer causality; default binding is local; no authentication exists; the read model contains no framework semantics.
- **Extension points:** Additive generic trace/span/parent/component/verification fields on the Workbench read model, API middleware for any future authentication, registered runners, replay-history storage, and reviewed built-in examples. Dynamic registration is not sandboxing, and future framework hierarchy remains adapter-side.
- **Tests:** [tests/test_dashboard.py](../tests/test_dashboard.py) and [tests/test_observability.py](../tests/test_observability.py).

## Examples

- **Responsibility:** Supply controlled, sanitized, offline demonstrations and case studies.
- **Important files:** [examples/weather/](../examples/weather/), [examples/rag-citation/](../examples/rag-citation/), [examples/tool-argument-safety/](../examples/tool-argument-safety/), and [src/traceforge/examples/](../src/traceforge/examples/), including the controlled portable execution-span example.
- **Inputs:** Versioned sealed capsules, separate regression specs, and recorded dependency fixtures.
- **Outputs:** Replay results, the end-to-end demonstration, and generated tests in temporary/ignored locations.
- **Invariants:** Controlled data only; no credentials, live calls, or unreviewed production traces; each expectation remains separate from evidence.
- **Extension points:** New reviewed case directories paired with a trusted runner and focused tests.
- **Tests:** [tests/test_case_studies.py](../tests/test_case_studies.py), [tests/test_replay.py](../tests/test_replay.py), and [tests/test_langgraph_integration.py](../tests/test_langgraph_integration.py).

## Go Gateway

- **Responsibility:** Accept bounded HTTP capture events, enforce media/body/schema/sensitive-value checks, expose health/readiness/metrics, enqueue asynchronously, propagate W3C context, and shut down within a bound.
- **Important files:** [main.go](../services/ingest-gateway/cmd/ingest-gateway/main.go), [config/](../services/ingest-gateway/internal/config/), [events/](../services/ingest-gateway/internal/events/), [httpapi/](../services/ingest-gateway/internal/httpapi/), [publisher/](../services/ingest-gateway/internal/publisher/), and [telemetry/](../services/ingest-gateway/internal/telemetry/).
- **Inputs:** `POST /v1/capture-events`, configured 0.2/0.3 schema files, and optional W3C headers.
- **Outputs:** HTTP `202/400/413/415/429/503`, Kafka records, bounded metrics, structured non-payload logs, and spans.
- **Invariants:** `202` means local queue acceptance only; queue full is `429`; unready is `503`; unsupported or version/type-mismatched events fail before enqueue; payloads and secrets do not enter logs/spans; health and readiness are distinct.
- **Extension points:** Publisher interface, configuration, validator versions, HTTP middleware, and telemetry setup owned by `main`.
- **Tests:** All `_test.go` files under [services/ingest-gateway/](../services/ingest-gateway/), especially HTTP, publisher outage/recovery, schema fixture, and telemetry tests.

## OpenTelemetry Collector and Metrics

- **Responsibility:** Optionally receive local OTLP, batch/export local traces, expose Collector health and Prometheus metrics, and verify cross-service correlation without changing capsules.
- **Important files:** [services/otel-collector.yaml](../services/otel-collector.yaml), [observability.py](../src/traceforge/observability.py), [metrics.py](../src/traceforge/metrics.py), and [scripts/gateway_smoke.py](../scripts/gateway_smoke.py).
- **Inputs:** OTLP gRPC/HTTP signals, W3C context, and optional SQLite capture correlation.
- **Outputs:** Local debug/file traces, Prometheus endpoints, and a sanitized ignored verification summary.
- **Invariants:** Disabled by default outside configured services; startup owns providers/exporters; no payloads, credentials, raw user text, or high-cardinality identifiers in metric labels; replay is a separate linked trace.
- **Extension points:** Service startup configuration, exporters after explicit approval, bounded metric families, and additional non-sensitive spans.
- **Tests:** [tests/test_observability.py](../tests/test_observability.py), Go telemetry/HTTP/publisher tests, and the explicit local smoke verifier.

## Docker and Compose

- **Responsibility:** Package the local dashboard/worker/gateway and orchestrate a single-node Kafka plus optional Collector topology.
- **Important files:** [Dockerfile](../Dockerfile), [Dockerfile.kafka](../Dockerfile.kafka), [services/ingest-gateway/Dockerfile](../services/ingest-gateway/Dockerfile), [compose.kafka.yml](../compose.kafka.yml), and [.dockerignore](../.dockerignore).
- **Inputs:** Repository source, pinned base/service images, Compose configuration, and an optional data-directory override.
- **Outputs:** Non-root application images, local services, Kafka named storage, and host-visible ignored capsule/SQLite/telemetry data.
- **Invariants:** Local development only; loopback host ports; no production orchestration claim; ordinary shutdown preserves data; telemetry profile is optional.
- **Extension points:** Local profiles and health checks. Deployment platforms require explicit milestone approval and ADRs.
- **Tests:** Image health commands, Compose smoke verification recorded in [verification-ledger.md](verification-ledger.md), and application/Go tests outside containers.

## Tests and CI

- **Responsibility:** Verify offline domain behaviour, adapters, dashboard, assembly/DLQ semantics, observability contracts, shared cross-language fixtures, and package installation.
- **Important files:** [tests/](../tests/), gateway `_test.go` files, and [.github/workflows/ci.yml](../.github/workflows/ci.yml).
- **Inputs:** Controlled fixtures and fake/local adapters.
- **Outputs:** Test, lint, package, and installed-CLI results.
- **Invariants:** Default tests are offline; no paid/live API calls; a passing fixture proves only its tested scope; evidence claims require ledger entries.
- **Extension points:** Focused regression tests adjacent to changed responsibilities and opt-in integration profiles.
- **Tests:** This component is the test inventory itself; portable-span schema, capture, integrity, replay non-dependence, transport, assembly, adversarial, and neutrality coverage is in [tests/test_execution_spans.py](../tests/test_execution_spans.py). See [testing-strategy.md](testing-strategy.md).

## Documentation

- **Responsibility:** Preserve product intent, decisions, current state, contributor memory, component ownership, evidence, and local runbooks without duplicate authorities.
- **Important files:** [PROJECT_MEMORY.md](../PROJECT_MEMORY.md), [docs/README.md](README.md), [project-state.md](project-state.md), ADRs, this map, [verification-ledger.md](verification-ledger.md), and [operations/](operations/).
- **Inputs:** Approved decisions, executed evidence, code responsibility changes, and verified failure modes.
- **Outputs:** Navigable current guidance and append-only/superseded historical records.
- **Invariants:** One owner per fact; link rather than copy; never silently rewrite historical evidence; no unsupported product or production claim.
- **Extension points:** New component documents, ADRs, ledger entries, and runbooks when the corresponding change is approved and verified.
- **Tests:** Internal-link/path validation, prohibited-claim scans, and `git diff --check`.

## Local Kubernetes Deployment

- **Responsibility:** Schedule, connect, configure, constrain, probe, restart, and persist the existing distributed containers on one dedicated local kind cluster.
- **Important files:** [Kustomize base](../deploy/kubernetes/base/kustomization.yaml), [kind overlay](../deploy/kubernetes/overlays/kind/kustomization.yaml), [kind cluster configuration](../deploy/kubernetes/overlays/kind/cluster.yaml), [lifecycle scripts](../scripts/kubernetes/), [smoke verifier](../scripts/kubernetes_smoke.py), and [Makefile](../Makefile).
- **Inputs:** Existing Dockerfiles and explicit image tags, non-sensitive ConfigMap values, the kind `standard` storage class, and the controlled weather fixture.
- **Outputs:** Gateway, Kafka, worker, API, and Collector workloads; only required Services; one local RWO PVC; and sanitized smoke/recovery results.
- **Invariants:** Deployment concerns never alter replay semantics; worker replicas remain one with `Recreate`; SQLite is single writer; application containers use UID/GID 10001; Kafka and Collector remain local-development infrastructure; no Secret, LoadBalancer, Ingress, Helm, cloud resource, or production claim is introduced. Every workload selects its dedicated ServiceAccount and disables token automount.
- **Extension points:** A separately approved overlay may change deployment configuration while preserving service and evidence boundaries. A cloud or production design requires measured need and a new or superseding ADR.
- **Tests:** [tests/test_kubernetes_assets.py](../tests/test_kubernetes_assets.py), `make kind-validate`, and the opt-in real `make kind-smoke` gate recorded in the [verification ledger](verification-ledger.md).

## Local Terraform Foundation

- **Responsibilities:** [infra/terraform/modules/kubernetes-foundation/](../infra/terraform/modules/kubernetes-foundation/) declares a reusable Namespace, ResourceQuota, LimitRange, five dedicated ServiceAccounts with token automount disabled, labels, and outputs. [infra/terraform/environments/kind/](../infra/terraform/environments/kind/) configures the pinned official Kubernetes provider for an explicit kubeconfig path and the fixed dedicated context.
- **Inputs:** typed namespace, labels, quota quantities, LimitRange defaults, kubeconfig path, and context. Validation rejects unsafe namespaces, unexpected contexts, incomplete ServiceAccount sets, and malformed/non-positive resource values.
- **Outputs:** namespace, merged foundation labels, ServiceAccount names/token settings, quota hard values, and LimitRange defaults. Terraform state is an ignored local operational artifact; `.terraform.lock.hcl` is committed.
- **Delivery boundary:** [deploy/kubernetes/foundation/kustomize/](../deploy/kubernetes/foundation/kustomize/) lets the ordinary kind overlay remain standalone. [deploy/kubernetes/overlays/terraform-kind/](../deploy/kubernetes/overlays/terraform-kind/) contains only Kustomize-owned workload objects and expects Terraform foundation objects. Both use the same base and [local component](../deploy/kubernetes/components/kind-local/).
- **Automation and tests:** [scripts/terraform/](../scripts/terraform/) guards init/plan/apply/drift/application-delete/destroy and proves rendered object sets are disjoint. Native mock-provider tests live under [environments/kind/tests/](../infra/terraform/environments/kind/tests/); Kubernetes asset tests cover both overlays.
- **Invariants:** Terraform never owns workloads, Services, ConfigMaps, PVC/application data, or cluster creation. Kustomize never owns foundation objects in the Terraform-backed overlay. No provisioner, shell substitute resource, secret input, cloud resource, or remote backend is present.
- **Extension seam:** another environment may call the module with a separately reviewed provider/backend design, but cloud resources and production state are not implied or approved. See [ADR-0006](decisions/ADR-0006-terraform-kustomize-ownership.md) and the [runbook](operations/terraform.md).
