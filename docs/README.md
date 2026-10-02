# Documentation Index

Read [PROJECT_MEMORY.md](../PROJECT_MEMORY.md) first. This directory is the authoritative map for TraceForge project knowledge. Avoid duplicating facts across documents: each decision or fact has one canonical owner, and other documents link to it.

## Canonical Documents

- [Start here](start-here.md): five-minute product, run, subsystem, reading, and invariant orientation.
- [Product](product.md): product problem, target developer, user workflow, guarantees, non-guarantees, and adoption criteria.
- [Architecture](architecture.md): replay and service boundaries, local Kubernetes deployment, future target architecture, and postponed infrastructure rationale.
- [Codebase map](codebase-map.md): current component responsibilities, inputs, outputs, invariants, extension points, and tests.
- [Weather replay spike](spikes/weather-replay.md): five-session feasibility spike plan, Weather Grounding Capsule scenario, offline requirements, and go/no-go criteria.
- [Roadmap](roadmap.md): evidence-based stage gates from documentation through possible infrastructure evaluation.
- [Project state](project-state.md): current phase, current milestone, repository status, assumptions, blockers, exact next approved task, and milestone-boundary checklist.
- [Testing strategy](testing-strategy.md): future test layers, what each layer proves, and what each layer does not prove.
- [Security](security.md): initial trust boundaries, capsule data risks, redaction requirements, safe fixtures, and local-first assumptions.
- [Glossary](glossary.md): TraceForge-specific definitions for replay, tracing, testing, and security terms.
- [Replay Capsule v0 contract](contracts/replay-capsule-v0.md): normative `0.1.0` document structure, replay semantics, validation boundaries, redaction, and integrity rules.
- [Replay Capsule 0.2.0 contract](contracts/replay-capsule-v0.2.md): successor schema with generic ordered tool dependencies, safe request identity, and bounded failure replay.
- [ADR-0001](decisions/ADR-0001-replay-first-product.md): accepted decision to build a replay-first product instead of a broad LangSmith clone.
- [ADR-0002](decisions/ADR-0002-replay-capsule-v0-format.md): accepted Replay Capsule v0 format, canonicalization, integrity, dependency normalization, and fail-closed fixture decisions.
- [ADR-0003](decisions/ADR-0003-capture-event-transport.md): accepted asynchronous capture-event envelope, ordering, idempotency, and evidence boundary.
- [ADR-0004](decisions/ADR-0004-repository-memory-and-navigation.md): accepted repository-memory authority, contributor reading order, and update contract.
- [ADR-0005](decisions/ADR-0005-local-kubernetes-kind-deployment.md): accepted native-Kustomize local kind deployment, security, persistence, and claim boundaries.
- [ADR-0006](decisions/ADR-0006-terraform-kustomize-ownership.md): accepted local Terraform foundation and disjoint Terraform/Kustomize object ownership.
- [ADR-0007](decisions/ADR-0007-replay-capsule-0.2-tool-dependencies.md): accepted `0.2.0` tool dependency, sanitization, compatibility, and failure semantics.
- [Go ingestion gateway](services/go-ingestion-gateway.md): local HTTP ingestion, validation, backpressure, and Kafka publishing semantics.
- [Observability](observability.md): optional local cross-service traces, replay links, metrics, verification commands, and security limitations.
- [Verification ledger](verification-ledger.md): commands and methods actually executed, results, environments, revisions, and limitations.
- [Git workflow](git-workflow.md): branch, commit, pull-request, release, rollback, artifact, and secret rules.
- [Changelog](../CHANGELOG.md): concise software release history; contract versions remain independent.
- [v0.4.1 release candidate notes](releases/v0.4.1.md): public release scope, evidence routing, artifacts, and limitations.
- [Local operations](operations/): development-only Kafka, gateway, worker, capsule, Collector, metrics, and SQLite runbooks.
- [Local Kubernetes operations](operations/kubernetes.md): dedicated kind lifecycle, port-forward access, verification, persistence, and failure triage.
- [Local Terraform operations](operations/terraform.md): guarded foundation plan/apply/state/drift/destroy lifecycle and ownership order.
- [Local dashboard](operations/dashboard.md): localhost workbench, trusted startup-only custom runner registration, and capture-to-replay workflow.

## Documentation Ownership and Update Table

| Document | Purpose | Authority | When it changes | Updater |
| --- | --- | --- | --- | --- |
| [PROJECT_MEMORY.md](../PROJECT_MEMORY.md) | Durable repository memory and mandatory reading contract | Long-term cross-document summary; links to detail owners | Durable boundaries/invariants, accepted ADR set, verified capability summary, milestone, next approved milestone, or reading contract changes | Contributor/agent completing the approved material change; maintainer reviews |
| [Root README](../README.md) | Public product and quick-start overview | Public entry point, not detailed status or evidence | Public workflow, install/run command, capability summary, or primary navigation changes | Contributor changing the public surface |
| [AGENTS.md](../AGENTS.md) | Codex execution rules | Mandatory agent governance | Repository safety, before/after-work contract, or product boundary changes | Maintainer approving agent policy |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Human contribution entry point | Contribution checklist | Branch, test, review, security, or documentation expectations change | Maintainer/contributor changing workflow |
| [Documentation index](README.md) | Canonical document navigation and ownership | Source-of-truth routing | A canonical document or ownership boundary is added, removed, or changed | Contributor making that documentation change |
| [Start here](start-here.md) | Five-minute contributor orientation | Navigation and runnable entry points only | Commands, subsystem locations, or mandatory warnings change | Contributor moving the entry point or subsystem |
| [Product](product.md) | Problem, user, workflow, guarantees, and non-guarantees | Product intent | Approved product boundary or success criterion changes | Product/maintainer decision owner |
| [Architecture](architecture.md) | System design and integration boundaries | Current/future architectural model | Service boundary, data flow, replay semantics, or layering changes | Implementer plus ADR author when required |
| [Codebase map](codebase-map.md) | Responsibility and extension map | Current repository structure | Responsibilities, inputs/outputs, invariants, extension points, or test locations move | Implementer making the move |
| [Project state](project-state.md) | Live phase, milestone, branch, blockers, assumptions, and exact next task | Current status | Every milestone completion, next-task change, blocker, or material assumption change | Contributor/agent completing that work |
| [Roadmap](roadmap.md) | Evidence-gated sequence | Stage ordering and gates | A stage gate or approved sequencing changes | Maintainer approving roadmap change |
| [Weather replay spike](spikes/weather-replay.md) | Original controlled feasibility plan | Historical spike scope and go/no-go criteria | Clarification or explicit supersession; do not rewrite the historical outcome | Spike owner/maintainer |
| [Testing strategy](testing-strategy.md) | Meaning and limits of test layers | Test claim boundaries | Test layer, offline rule, or evidence interpretation changes | Test/feature implementer |
| [Verification ledger](verification-ledger.md) | Executed evidence | Verification claims | Immediately after a relevant command/method is actually executed | Person/agent who executed it |
| [Security](security.md) | Trust boundaries and fixture safety | Security model | Data flow, secret risk, auth, telemetry, storage, or redaction boundary changes | Implementer plus security reviewer |
| [Replay Capsule contract](contracts/replay-capsule-v0.md) | Normative capsule semantics | Format contract for `0.1.0` | Compatible clarification only; incompatible changes require a new version and ADR | Contract owner/maintainer |
| [Replay Capsule 0.2.0 contract](contracts/replay-capsule-v0.2.md) | Normative generic-tool capsule semantics | Format contract for `0.2.0` | Compatible clarification only; incompatible changes require a new version and ADR | Contract owner/maintainer |
| [ADRs](decisions/) | Historical architectural decisions | Decision rationale and status | New decision or explicit supersession; accepted history is not silently rewritten | Decision owner/reviewers |
| [Local Kubernetes operations](operations/kubernetes.md) | kind deployment and recovery procedure | Dedicated cluster lifecycle, access, persistence, and bounded verification | Manifest, lifecycle command, local failure mode, or recovery path changes | Kubernetes milestone implementer/operator |
| [Local Terraform operations](operations/terraform.md) | local foundation lifecycle | Provider/state design, plan/apply/drift/destroy, and Terraform/Kustomize ownership order | Module, environment, state, provider, ownership, guard, or recovery path changes | Terraform milestone implementer/operator |
| [Go gateway](services/go-ingestion-gateway.md) | Gateway behaviour | Component detail | HTTP, validation, readiness, queueing, Kafka, or shutdown behaviour changes | Gateway implementer |
| [LangGraph migration](integrations/langgraph-migration.md) | Optional integration seam | Integration guidance | Adapter/package boundary or supported migration workflow changes | Framework integration implementer |
| [Observability](observability.md) | Trace, link, metric, and telemetry security model | Observability detail | Span/metric model, configuration, verifier, or limitation changes | Observability implementer |
| [Operations](operations/) | Local failure triage | Verified development runbooks | A new failure mode/recovery path is verified or a command changes | Implementer/operator who verified it |
| [Git workflow](git-workflow.md) | Contribution and release mechanics | Repository Git policy | Branch, review, CI, tag, rollback, artifact, or secret policy changes | Maintainer |
| [Glossary](glossary.md) | Stable project terminology | Term definitions | A durable term is added or meaning changes | Author introducing the term |

Update the canonical owner first, then update memory/navigation references. Do not add a second status file, decision log, verification summary, or competing source of truth.
