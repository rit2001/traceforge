# Product

## Problem Statement

AI-agent failures are difficult to debug because they depend on a changing mix of prompts, model outputs, tool calls, tool responses, graph state, external APIs, and developer intent. A failure can disappear when rerun, or a fix can appear to work only because the external facts or model response changed.

TraceForge focuses on one narrow problem: preserve a failed agent execution well enough that a developer can replay it, fork it under controlled conditions, compare the paths, and turn approved expected behaviour into an offline regression test. The product vision includes production failures later, but the initial feasibility spike uses a controlled local failure unless a genuine production failure is explicitly supplied.

## Implementation Status

- **Implemented:** controlled capture, sanitization, sealing, structural/semantic/integrity validation, exact offline replay, portable structured diff and bounded divergence analysis, separate developer-approved regression specifications, explicit promotion from a supplied completed result, server-replayed Workbench bundles, and pytest export.
- **Partial:** capture and framework integration remain bounded, while Replay Capsule `0.2.0` provides a framework-independent generic tool dependency primitive.
- **Planned:** broader real-agent integration, fork replay, and opt-in fresh-model replay.

The generic tool primitive accepts exact-replay evidence only when the standard scanner leaves a
tool result unchanged as JSON. If not, the application still receives the original successful
result, but the pending `CaptureSession` cannot produce a capsule draft. No generic result
projection/sanitizer API exists in v0.5.

TraceForge's evidence and replay semantics are framework-agnostic. LangGraph is the first real
integration proof; its graph, node, state, and callback concepts are translated by an adapter and
do not define the capture core, Replay Capsule, replay, regression, or future core diff model.

## Target Developer

The initial target developer builds Python LangGraph or tool-calling agents locally and needs to debug a concrete failed run. They are comfortable reading traces, prompts, tool payloads, and test output. They want reproducible regression coverage before changing prompts, graph nodes, or tool adapters.

## Failure Categories

TraceForge initially targets failures such as:

- Incorrect tool choice.
- Incorrect tool arguments.
- Correct tool response followed by incorrect reasoning.
- Missing grounding in tool output.
- Unexpected graph branch or termination.
- Prompt or graph changes that regress a previously fixed behaviour.
- Non-deterministic model output that makes a failure hard to reproduce.

It does not initially target infrastructure outages, fleet observability, cost analytics, production alerting, or automatic repair.

## Replay Capsule Definition

A Replay Capsule is a local artifact that freezes the information needed to replay and compare a specific agent execution. For the feasibility spike, a capsule should include:

- Invocation input.
- Subject application and descriptive framework provenance.
- Prompt and message history relevant to the run.
- Model request metadata.
- Captured model outputs.
- Tool call names, arguments, and call order.
- Captured tool outputs.
- Ordered, framework-neutral execution events.
- Timestamps or ordering metadata where needed for comparison.
- Redaction metadata for sensitive fields.

Developer-approved expectations are deliberately stored in a separate regression specification. They are not capsule evidence and do not change capsule integrity.

The capsule is not a general data lake, hosted trace store, or production telemetry backend.

Capsules must never contain API keys, secrets, authorization headers, or unredacted sensitive data.

## Implemented User Workflow

1. A developer observes a failed local agent run.
2. TraceForge captures the run into a Replay Capsule.
3. The developer runs exact replay to confirm the captured failure path can be reproduced offline.
4. TraceForge compares the original and replayed observations.
5. The developer understands the bounded diff and analysis without treating them as root cause.
6. The developer explicitly promotes only selected, reviewed expectations into the separate
   regression specification.
7. Workbench replays the current evidence again and returns one coherent artifact bundle, or trusted
   local code exports the approved specification through the existing pytest pipeline.
8. Future changes are checked in local or CI pytest without calling live application dependencies.

In shorthand: **Capture → Replay → Understand → Promote → CI**. Promotion never mutates historical
evidence and a replay that differs from the historical failure remains eligible when its selected
repaired behavior is correct.

## Planned Fork Workflow

A future fork replay will keep recorded tool/dependency outcomes fixed while allowing model, prompt, graph, or agent behavior to run again. Any fresh-model execution will be explicit and opt-in, may consume API quota, and must never run silently in default CI. Fork replay is not implemented in `v0.4.1`.

## Product Guarantees

The implemented exact-replay path guarantees for tested adapters that:

- Exact replay does not call live model or tool APIs.
- Exact replay uses captured model and tool outputs.
- Unit and CI test suites remain fully offline by default.
- Unit tests use fake or recorded model adapters and recorded tool responses.
- Exported tests can run offline.
- AI-generated assertions are not accepted without developer approval.
- Sensitive values are not intentionally copied from external application repositories.

A future fork-replay implementation must use captured tool/dependency outcomes and state its probabilistic boundaries explicitly.

## Product Non-Guarantees

TraceForge does not guarantee:

- Automatic fixes.
- Elimination of hallucinations.
- Production incident detection.
- Full determinism for new model generations in fork replay.
- Prompt-quality improvement from fake-model tests alone.
- Compatibility with every agent framework.
- Hosted storage, authentication, billing, or collaboration features.
- Accurate behaviour if the original capture omitted required data.

## Initial Success Criteria

The initial controlled spike established these implemented mechanics:

- A controlled local LangGraph weather-agent failure can be represented as a sanitised Replay Capsule without copying application code or secrets.
- Exact replay reproduces the captured execution path offline.
- Deterministic comparison identifies supported observation and output differences.
- A developer-approved expectation can be exported as an offline regression test.
- A technically completed repaired replay can be explicitly promoted into the existing regression
  specification without requiring deterministic equality or changing the capsule.

Fork replay with frozen tool outputs and richer execution diffing remain planned success criteria rather than completed evidence.

Prompt-quality claims require measured live evaluation results. A fake model can validate replay-engine mechanics, but it cannot prove that a prompt change improves real model behaviour.
