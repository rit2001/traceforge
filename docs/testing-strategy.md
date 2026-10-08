# Testing Strategy

TraceForge has Python and Go implementation tests plus bounded local Compose and kind smoke verification. This document defines the test layers and the limits of what each layer can prove. Only executed results recorded in the [verification ledger](verification-ledger.md) are verification evidence.

Default local and CI tests must make no paid API calls, no live model calls, and no live tool calls.

## Fast Unit Tests

Purpose:

- Validate small local functions and replay-engine mechanics.
- Use fake or recorded model adapters.
- Use recorded tool responses.

Proves:

- Local logic behaves as expected for known inputs.
- Replay components can handle expected capsule shapes.

Does not prove:

- A real model behaves better.
- A prompt improves real-world behaviour.
- The integration with Agentic-chatbot works end to end.

Current coverage includes both capsule versions, generic tool capture/replay, sensitive-identity
rejection, mutating-sanitizer isolation, result-evidence invalidation without changing live tool
success, exact replay failure modes, capture/redaction, regression/export, dashboard, capture-event
schemas, Kafka publisher/assembly/DLQ semantics, OpenTelemetry correlation, metric-label bounds,
and the Go gateway's validation, HTTP, publisher, telemetry, and outage/recovery boundaries.

Regression-promotion coverage requires explicit approval and selected assertions, accepts a
repaired replay whose observation differs from history, rejects technical failure, proves no
capsule/diff/analysis mutation, reuses the existing regression operators, refuses implicit broad
snapshots, rejects non-JSON values and exact duplicates, covers no prior spec and failed old specs,
checks atomic bundle collision safety, and runs the controlled generated pytest through pass →
intentional regression failure → restored pass → dependency mismatch with recorded dependencies
only.

## Exact Offline Replay Tests

Purpose:

- Run exact replay against sanitized fixtures.
- Confirm that recorded model outputs and recorded tool outputs are used correctly.

Proves:

- Captured paths can be reproduced offline.
- Exact replay mechanics, recorded-dependency injection, and deterministic assertions work for the fixture.

Does not prove:

- Production readiness.
- Broad framework compatibility.
- Live model quality.

## Planned Fork Replay Tests

Fork replay is not implemented in `v0.4.1`. When that mode exists, separate offline tests should freeze recorded tool/dependency outcomes while exercising an explicit fake or recorded model adapter. Opt-in live-model experiments must remain outside default tests and CI.

## Future Integration Tests Against Agentic-chatbot

Purpose:

- Verify that Agentic-chatbot can install and use the local TraceForge package/API on a dedicated integration branch.
- Confirm that the client application can record and export a sanitized Replay Capsule.

Proves:

- The integration boundary works for the system under test.
- Capture/export behaviour can operate from the client application.

Does not prove:

- TraceForge works with all LangGraph applications.
- Secrets are safe without a redaction review.
- Hosted or distributed operation is needed.

## Opt-In Live Model Experiments

Purpose:

- Run live fork experiments with recorded tool outputs and a real explicitly configured model.
- Measure whether prompt or model changes improve the scenario.

Proves:

- Only the measured behaviour for the configured model, prompt, and scenario.
- Whether a prompt-quality claim has supporting live evidence.

Does not prove:

- Deterministic correctness.
- Hallucination elimination.
- Suitability for default CI.

Live experiments may consume API quota and must never run silently in default CI.

## Security and Redaction Tests

Purpose:

- Check that capsules and fixtures do not include secrets, authorization headers, API keys, or unredacted sensitive data.
- Validate redaction behavior around prompts, tool arguments, tool outputs, and user data.

Proves:

- Known sensitive patterns and configured redaction rules are enforced for tested cases.

Does not prove:

- Production security certification.
- That every possible secret format is detected.
- That unsanitized production traces are safe to commit.

Fake-model tests validate mechanics, not real model quality. Do not invent benchmark, coverage, reliability, or adoption claims from these tests.

## Local Distributed Smoke Tests

Purpose:

- Verify one bounded HTTP-to-Go-to-Kafka-to-Python-to-sealed-capsule-to-replay path.
- Verify optional W3C propagation, a separate replay Span Link, local metrics endpoints, duplicate handling, and a bounded sensitive-attribute scan.

Proves:

- The tested local single-node topology connects the implemented components for the controlled scenario.

Does not prove:

- Production readiness, scale, long-running durability, exactly-once processing, universal secret absence, or operational recovery objectives.

Integration commands are opt-in because they require a local Docker daemon. They must not make paid calls or contact external application/model APIs.

## Local Kubernetes Gate

Purpose:

- Render and apply the Kustomize kind overlay around the existing images.
- Verify workload readiness, one real capture/replay path, pod recreation, PVC survival across worker replacement, and effective non-root application identities.
- Check static manifest invariants for explicit images, resources, probes, security contexts, Services, local-infrastructure labels, and dedicated-cluster automation.

Proves:

- The tested ARM64 Docker/kind/Kubernetes versions can run the five-workload local topology for one controlled scenario.
- Kubernetes recreates the selected stateless pod and reattaches the local PVC to a replacement worker in this single-node cluster.

Does not prove:

- Cloud compatibility, multi-node scheduling, high availability, scale, Kafka durability, storage disaster recovery, authentication, TLS, or production security.
- That a worker metrics probe detects stalled Kafka consumption; the end-to-end smoke supplies the bounded consumption evidence.

The gate is opt-in, requires Docker and kind, uses no paid or external application API, and must delete the dedicated cluster after evidence is collected.

## Local Terraform Gate

Fast native tests under `infra/terraform/environments/kind/tests/*.tftest.hcl` use a mock Kubernetes provider. They check default names/labels, the exact ServiceAccount set, disabled token automount, quota and LimitRange values, outputs, and rejection of invalid namespace, context, quota, and LimitRange inputs. CI runs format, backend-free initialization, validation, and mock tests without Docker, kind, cloud credentials, or infrastructure creation.

The opt-in real gate initializes the pinned provider, plans and applies eight foundation resources to the dedicated kind context, inspects state, applies the Terraform-backed Kustomize overlay, and runs the existing application smoke once. `plan -detailed-exitcode` must return 0 after apply, 2 after a controlled disposable namespace-label change, and 0 after reconciliation. Cleanup removes Kustomize objects first, destroys Terraform resources, verifies empty state/absent namespace, and destroys the dedicated cluster.

This proves the tested local provider/state lifecycle and ownership boundary for one kind cluster. It does not prove remote-state operation, cloud compatibility, AWS/EKS, concurrent operators, production recovery, availability, scale, or security. Mock-provider tests do not prove API-server behaviour; the real gate supplies that bounded evidence.
