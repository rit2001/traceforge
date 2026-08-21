# TraceForge Roadmap

TraceForge advances through evidence-based milestones. An item is implemented only when code, tests, and the relevant operational or contract documentation agree. Dates are intentionally omitted until scope is approved and verifiable.

## Current Implementation

The `v0.4.1` line contains the replay-first local core and a bounded optional distributed-ingestion path. Exact replay, regression evaluation, pytest export, the controlled examples, local workbench, Go/Kafka/Python assembly path, bounded OpenTelemetry/Prometheus instrumentation, Docker Compose, local kind/Kustomize, and the narrow local Terraform foundation have implementation evidence.

Capture remains controlled rather than generic. Fork replay, fresh-model replay, production infrastructure, hosted operation, and benchmark claims are not implemented.

## v0.4.1 — Public Beta

Goal: publish the current replay-first system as a clean, accurate Experimental Beta.

Included:

- Replay Capsule `0.1.0`, sealing, integrity, and validation;
- deterministic exact offline replay of recorded model and HTTP outcomes;
- deterministic comparison, separate developer-approved regression specifications, and pytest export;
- CLI, local FastAPI replay workbench, SQLite replay history, and controlled examples;
- bounded Go ingestion gateway → Kafka → Python assembly worker path;
- local W3C propagation, optional OpenTelemetry spans, and Prometheus metrics;
- Docker Compose, native kind/Kustomize, and narrow local Terraform foundation;
- public documentation, contributor framework, and release verification.

This milestone does not include fork replay, a generic capture SDK, production deployment, or performance claims.

## v0.5.0 — Real Agent Capture

Primary goal: prove TraceForge against one real, sanitized LangGraph agent application without broadening the product boundary prematurely.

Planned work:

- stabilize the capture API around the evidence needed by replay;
- integrate one real LangGraph application using sanitized data;
- strengthen framework capture while preserving explicit boundaries;
- define and implement a generic tool dependency contract;
- connect `CaptureSession` to the event transport in an intentional integration path;
- introduce a richer, reviewable execution diff; and
- publish a reproducible integration tutorial.

Exit evidence should include an offline, sanitized capture → seal → exact replay → regression path for the selected application. This is not a claim of arbitrary Python or LangGraph support.

## v0.6.0 — Fork Replay

Primary goal: implement an explicit replay mode that can change model or prompt behavior while freezing approved dependency outcomes.

Planned work:

- specify and implement fork replay semantics;
- freeze recorded tool and dependency outcomes;
- make fresh-model execution explicit, opt-in, and excluded from default CI;
- compare messages, tool calls, graph nodes, and execution paths;
- improve replay comparison output; and
- define a proposal/review workflow for regression expectations.

All items in this milestone are **planned**. Exact replay remains the only implemented replay mode in `v0.4.1`.

## v0.7.0 — Pipeline Reliability

Primary goal: make the bounded local event pipeline's failure and recovery behavior explicit and testable.

Planned work:

- producer retry semantics;
- bounded shutdown draining;
- worker readiness;
- Kafka consumer-lag metrics;
- DLQ inspection and redrive;
- multi-partition behavior;
- consumer rebalance tests;
- bounded Kafka outage and recovery tests; and
- measured backpressure validation.

The transport will continue to be described as at least once unless stronger semantics are both designed and proven. Domain idempotency remains distinct from Kafka delivery semantics.

## v0.8.0 — Measurement

Primary goal: establish repeatable evidence about capacity and operational behavior before making performance claims.

Planned work:

- a reproducible benchmark harness and documented environment controls;
- ingestion throughput and replay latency measurement;
- p50, p95, and p99 reporting;
- CPU and memory observation;
- large-capsule behavior;
- bounded soak tests;
- outage recovery measurement; and
- explicit capacity assumptions and limitations.

No throughput, latency, scale, or reliability target is claimed before this evidence exists.

## Target Architecture

The near-term target preserves a replay-first local core while making real-agent capture and dependency adapters more general. The optional distributed path remains a transport and assembly boundary, not a replacement for Replay Capsule semantics.

Cloud deployment, high availability, multi-tenancy, authentication, distributed trace search, ClickHouse, SaaS billing, and production Kubernetes/Terraform are outside these approved milestones.

## Open Questions

- What is the smallest generic dependency contract that supports tool-calling agents without hiding side effects?
- Which LangGraph integration seam can remain stable without claiming universal framework coverage?
- How should fork replay make probabilistic fresh-model execution visible in results and CI policy?
- Which execution differences are useful enough to review without coupling the capsule to one framework?
- What operational evidence is required before expanding the local Kafka topology?

No `v1.0` milestone is defined.
