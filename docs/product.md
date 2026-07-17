# Product

## Problem Statement

AI-agent failures are difficult to debug because they depend on a changing mix of prompts, model outputs, tool calls, tool responses, graph state, external APIs, and developer intent. A failure can disappear when rerun, or a fix can appear to work only because the external facts or model response changed.

TraceForge focuses on one narrow problem: preserve a failed agent execution well enough that a developer can replay it, fork it under controlled conditions, compare the paths, and turn approved expected behaviour into an offline regression test. The product vision includes production failures later, but the initial feasibility spike uses a controlled local failure unless a genuine production failure is explicitly supplied.

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
- Agent and graph metadata.
- Prompt and message history relevant to the run.
- Model request metadata.
- Captured model outputs.
- Tool call names, arguments, and call order.
- Captured tool outputs.
- Execution path and node transitions.
- Timestamps or ordering metadata where needed for comparison.
- Redaction metadata for sensitive fields.
- Developer-approved expectations when a test is exported.

The capsule is not a general data lake, hosted trace store, or production telemetry backend.

Capsules must never contain API keys, secrets, authorization headers, or unredacted sensitive data.

## User Workflow

1. A developer observes a failed local agent run.
2. TraceForge captures the run into a Replay Capsule.
3. The developer runs exact replay to confirm the captured failure path can be reproduced offline.
4. The developer runs an offline fork replay after changing a prompt, graph edge, model setting, or other local behaviour while keeping tool outputs fixed and using a fake or recorded model adapter.
5. TraceForge compares the original and replayed paths.
6. The developer reviews suggested expectations or writes their own.
7. Approved expectations are exported as an offline regression test.
8. Future changes are checked against that regression test without calling live APIs.
9. Separately, the developer may opt into a live fork experiment with a real explicitly configured model and recorded tool outputs. This may consume API quota and must not run silently in default CI.

## Product Guarantees

TraceForge should guarantee, once implemented and tested, that:

- Exact replay does not call live model or tool APIs.
- Exact replay uses captured model and tool outputs.
- Fork replay uses captured tool outputs.
- Unit and CI test suites remain fully offline by default.
- Unit tests use fake or recorded model adapters and recorded tool responses.
- Exported tests can run offline.
- AI-generated assertions are not accepted without developer approval.
- Sensitive values are not intentionally copied from external application repositories.

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

## Initial Adoption and Success Criteria

Initial adoption should be measured through the feasibility spike, not broad claims. The first success criteria are:

- A controlled local LangGraph weather-agent failure can be represented as a sanitised Replay Capsule without copying application code or secrets.
- Exact replay reproduces the captured execution path offline.
- Fork replay reuses frozen tool outputs while allowing model or prompt behaviour to change.
- The comparison identifies meaningful path or output differences.
- A developer-approved expectation can be exported as an offline regression test.
- The approach is small enough to justify implementation before adding infrastructure.

Prompt-quality claims require measured live evaluation results. A fake model can validate replay-engine mechanics, but it cannot prove that a prompt change improves real model behaviour.
