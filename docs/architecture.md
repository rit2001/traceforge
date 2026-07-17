# Architecture

## Feasibility-Spike Architecture

The spike architecture is local, narrow, and file-based. Its purpose is to prove that replay is useful before building a platform.

Core components:

- Capture: records a failed local LangGraph or tool-calling execution.
- Replay Capsule: stores captured inputs, graph metadata, model outputs, tool calls, tool outputs, execution path, and comparison metadata.
- Exact replay: replays the execution with frozen model and tool outputs.
- Offline fork replay: reuses frozen tool outputs while allowing prompt or graph mechanics to run against fake or recorded model adapters.
- Live fork experiment: reuses frozen tool outputs while running a real explicitly configured model.
- Diff: compares execution paths, node transitions, model-visible facts, and outputs.
- Test export: turns developer-approved expectations into offline regression tests.

The spike should avoid services, message queues, distributed storage, hosted dashboards, and production deployment assumptions.

## Future Target Architecture

If the replay spike passes, the target architecture may expand around the same replay-first core:

- Capture adapters for additional Python agent frameworks.
- A stable Replay Capsule schema with migration support.
- A local CLI and library API.
- A Python package/API that client applications can install locally.
- Richer diff views for graph paths, messages, tool calls, and assertions.
- Test exporters for common Python test frameworks.
- Optional storage, indexing, or team workflows only after real usage requires them.

The target architecture still remains distinct from a generic observability product. Replay, comparison, and regression-test export remain the product center.

## Capture

Capture should collect enough data to replay and compare a failed execution without requiring live external dependencies. For the first milestone, capture can be explicit and framework-specific rather than magical or universal.

Captured data should include:

- Initial user input and run configuration.
- Graph or agent node metadata.
- Prompt and message state.
- Model request metadata and captured responses.
- Tool call names, arguments, ordering, and captured outputs.
- Execution path and terminal state.
- Errors and exceptions when relevant.
- Redaction decisions or markers.

## Replay Capsule

The Replay Capsule is the boundary between capture, replay, diff, and test export. It should be portable enough for offline tests, but not treated as a production telemetry format during the spike.

Capsules must not require `.env` files, live API credentials, or access to the original application repository secrets.

Capsules must never contain API keys, secrets, authorization headers, or unredacted sensitive data. A sanitised capsule fixture may be stored in TraceForge for offline tests.

## Agentic-chatbot Integration Boundary

TraceForge and Agentic-chatbot remain separate repositories. TraceForge may eventually expose a Python package/API that Agentic-chatbot installs locally on a dedicated integration branch.

The client application is responsible for recording and exporting a sanitised Replay Capsule through that integration. TraceForge must not hard-code an absolute path to Agentic-chatbot, copy Agentic-chatbot source code, or move integration-specific end-to-end changes into the TraceForge repository.

A sanitised capsule fixture may live in TraceForge for offline tests after review. End-to-end integration changes remain in Agentic-chatbot.

## Exact Replay

Exact replay freezes both model outputs and tool outputs. It checks whether the captured execution path can be reproduced from the capsule without live services.

This is the baseline reproducibility check. If exact replay cannot reproduce the captured path, fork replay and test export are not trustworthy.

## Fork Replay

Fork replay freezes tool outputs while allowing model or prompt behaviour to run again. This isolates whether a prompt, graph, or model change would behave differently against the same external facts.

Offline fork replay uses fake or recorded model adapters and recorded tool responses. It can validate replay-engine mechanics such as state reconstruction, graph path handling, tool-output injection, and diff generation.

A live fork experiment uses a real explicitly configured model with recorded tool outputs. It is opt-in, may consume API quota, and must never run silently in default CI.

Live fork replay can be probabilistic because model generation may vary. Comparisons must account for that limitation and avoid overstating determinism.

## Diff

Diff should compare behaviour at levels useful to a developer:

- Node path and graph branches.
- Tool choice and tool arguments.
- Tool outputs shown to the model.
- Model messages and final answer.
- Approved expectations and assertion results.

The first diff can be textual and structured rather than a full dashboard.

## Test Export

Test export converts developer-approved expectations into offline tests. Generated or suggested assertions are drafts until the developer approves them.

Tests should depend on the Replay Capsule and local TraceForge code, not live model APIs, live tool APIs, application secrets, or external services.

Default unit and CI test suites must remain fully offline. Live fork experiments are evaluation runs, not default regression checks.

## Deterministic Versus Probabilistic Checks

Deterministic checks are suitable for exact replay and frozen data:

- Same captured tool output.
- Same captured model output.
- Same graph path under frozen responses.
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

## Postponed Infrastructure

Kafka is postponed because the spike does not need distributed event streaming. A local capture and replay loop is enough to test the core product risk.

Go is postponed because the first supported developers and client agent are Python-based. Adding another implementation language would increase coordination cost before replay feasibility is proven.

ClickHouse is postponed because the product is not yet a large-scale observability database. Local Replay Capsules and offline tests should prove value before analytical storage is considered.

Terraform, Kubernetes, SaaS authentication, and payments are also postponed because deployment and monetization are not the current risk. Replay feasibility is.
