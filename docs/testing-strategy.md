# Testing Strategy

TraceForge has no implementation tests yet. This document defines future testing layers and the limits of what each layer can prove.

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

## Offline Replay Tests

Purpose:

- Run exact replay and offline fork replay against sanitized fixtures.
- Confirm that recorded model outputs and recorded tool outputs are used correctly.

Proves:

- Captured paths can be reproduced offline.
- Replay mechanics, tool-output injection, and deterministic assertions work for the fixture.

Does not prove:

- Production readiness.
- Broad framework compatibility.
- Live model quality.

## Integration Tests Against Agentic-chatbot

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
