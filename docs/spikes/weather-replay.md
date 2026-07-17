# Weather Replay Feasibility Spike

## Goal

Prove that TraceForge can capture and replay a controlled local LangGraph weather-agent failure using the existing Agentic-chatbot repository as the system under test, without copying application code, exposing secrets, or making live API calls in default tests.

The existing LangGraph/OpenWeather agent is the system under test. TraceForge should interact with it through approved local boundaries only. The initial fixture is not a production incident unless a genuine production failure is later supplied.

## Five Focused Sessions

### Session 1: Failure Framing

- Identify one concrete weather-agent failure mode.
- Define the user input, expected behaviour, observed wrong behaviour, and relevant graph path.
- Confirm that no secrets or `.env` files are needed for the written spike artifacts.
- Confirm that the scenario is labelled as a controlled local failure unless genuine production evidence is supplied.

### Session 2: Capture Shape

- Define the Weather Grounding Capsule structure.
- List required model messages, tool calls, OpenWeather tool outputs, graph transitions, and final output fields.
- Decide which fields need redaction markers.

### Session 3: Exact Replay

- Replay the captured execution using frozen model outputs and frozen OpenWeather tool outputs.
- Verify that exact replay does not call live APIs.
- Confirm that the replayed path matches the captured failed path.

### Session 4: Fork Replay and Diff

- Freeze OpenWeather tool outputs.
- Allow the prompt or graph path to run again under controlled offline execution with a fake or recorded model adapter.
- Compare original and forked paths, tool use, grounding behaviour, and final answer.
- Keep any live fork experiment separate, opt-in, and outside default CI.

### Session 5: Test Export

- Convert developer-approved expected behaviour into an offline regression test.
- Verify the test fails against the known bad behaviour and passes against the fixed behaviour when available.
- Document go/no-go evidence.

## Weather Grounding Capsule Scenario

The spike scenario is a controlled local weather question where the agent receives recorded weather data from an OpenWeather-backed tool but produces an answer that is not grounded in the returned data. The capsule should preserve the external weather facts and the agent path so the failure can be reproduced and compared offline.

## Required Captured Data

- User input.
- Agent or graph version metadata available without copying application code.
- LangGraph node sequence.
- Prompt and message history relevant to the weather answer.
- Model request metadata.
- Captured model outputs for exact replay.
- Tool call name, arguments, and call order.
- Captured OpenWeather tool output.
- Final answer.
- Error or mismatch notes.
- Redaction markers for any sensitive or environment-derived fields.

Captured data must exclude API keys, secrets, authorization headers, and unredacted sensitive data.

## Definition of Fixed Behaviour

Fixed behaviour means the final answer is grounded in the captured weather tool output and follows the developer-approved expectation for the scenario. The expected behaviour must be reviewed and approved by a developer before it becomes a regression test.

For example, a fixed answer should not invent weather conditions, temperatures, locations, timestamps, or recommendations that are unsupported by the captured OpenWeather output.

## Offline Test Requirements

- Tests must not call OpenWeather.
- Tests must not call model APIs.
- Tests must not require `.env` files.
- Tests must not require secrets.
- Tests must run from captured capsule data and local code only.
- Unit tests must use fake or recorded model adapters and recorded tool responses.
- Tests must make approval status explicit for generated assertions.

Live fork experiments may use a real explicitly configured model with recorded tool outputs, may consume API quota, and must never run silently in default CI.

## Go/No-Go Criteria

Go if:

- A representative weather-agent failure can be captured into a capsule.
- Exact replay reproduces the captured path offline.
- Offline fork replay can reuse frozen OpenWeather output while validating replay-engine mechanics with a fake or recorded model adapter.
- Diff output helps identify the behavioural difference.
- A developer-approved expectation can be exported as an offline regression test.
- Any prompt-quality claim is backed by measured live evaluation results, not fake-model tests alone.

No-go or revisit if:

- Required capture data cannot be obtained without invasive changes to the client application.
- Exact replay cannot be made reliable enough for the captured scenario.
- The capsule requires secrets or `.env` access.
- The capsule would contain API keys, secrets, authorization headers, or unredacted sensitive data.
- Offline tests cannot represent the fixed behaviour.
- The implementation scope expands into infrastructure before the replay loop is proven.

## Known Limitations

- The spike covers one weather-agent scenario, not all agent failures.
- The initial fixture is a controlled local failure, not demonstrated production capability.
- Offline fake-model replay cannot prove that a new prompt improves real model behaviour.
- Live fork replay may remain probabilistic when a real model is allowed to generate fresh text.
- The spike does not prove production scalability.
- The spike does not provide hosted observability.
- The spike does not guarantee hallucination elimination.
- The spike does not establish support for non-Python ecosystems.
