# Glossary

## Trace

A recorded view of one agent execution, including the inputs, model interactions, tool calls, tool outputs, graph transitions, and final result needed to understand what happened.

## Span

A bounded part of a trace, such as one graph node, model call, tool call, or replay step. Spans help compare where two executions diverged.

## Event

A discrete recorded fact inside a trace, such as a tool call being issued, a model response being received, a graph branch being taken, or an assertion being evaluated.

## Replay Capsule

A local artifact that contains the sanitized data needed to reproduce and compare one captured agent execution without depending on live external services.

## Exact Replay

A replay mode that uses recorded model outputs and recorded tool outputs to reproduce the captured execution path offline.

## Fork Replay

A replay mode that keeps tool outputs recorded while allowing prompt, graph, or model behaviour to run again under controlled conditions.

## Fixture

A reviewed local test artifact, such as a sanitized Replay Capsule, used to run offline tests without secrets or live API calls.

## Deterministic Assertion

An assertion whose result should be stable for the same recorded data, such as matching a graph path, tool call argument, or approved final-answer field.

## Probabilistic Evaluation

An opt-in evaluation involving fresh model generation where results may vary and must be measured rather than treated as a guaranteed regression check.

## Regression Test

An offline test created from developer-approved expected behaviour to detect whether a future code, prompt, or graph change breaks that behaviour.

## Redaction

Removing or replacing sensitive values before data is stored in a capsule or fixture, including API keys, authorization headers, secrets, and unneeded user data.

## System Under Test

The agent application being examined by TraceForge. For the first spike, this is the LangGraph/OpenWeather agent in Agentic-chatbot.

## Adapter

A small boundary layer that lets TraceForge capture or replay interactions with an external component such as a model, tool, graph framework, or client application.

## Nondeterminism

Behaviour that may differ between runs even with similar inputs, often because model generation, timing, external data, or tool responses can vary.

## Grounding

The requirement that an agent answer be supported by the captured tool output or other recorded facts, rather than invented or inferred from unavailable information.
