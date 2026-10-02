# LangGraph Migration Guide

TraceForge's core package does not import LangGraph. Install the optional integration with `pip install "traceforge-replay[langgraph]"`.

LangGraph is an integration proof, not TraceForge's domain model. The adapter owns all translation
from `StateGraph`, nodes, graph state, and callbacks into generic invocation, dependency, ordered
event, and observation values. Do not add LangGraph types or semantics to capture core, Replay
Capsule schemas, sealing, validation, replay, regression, or core diff code. If the integration
appears to need such a change solely because of LangGraph's API shape, stop and redesign the
adapter boundary.

The first real Agentic-chatbot integration keeps application ownership in that repository and
uses these boundary changes:

1. Create a `CaptureSession` when a graph run begins, using sanitized run/application metadata. Use Replay Capsule `0.2.0` when the run records a generic tool dependency.
2. Wrap the existing injected model and HTTP clients with `record_model` and `record_http`. Wrap application tools with `record_tool`, and supply an application-owned deterministic argument sanitizer when default scanning would alter request identity. Keep provider-specific clients outside TraceForge core.
3. Translate any relevant node transitions into portable `record_event` values inside the adapter;
   the event envelope itself must not require LangGraph node semantics. Then call `finish` and
   `seal_capsule` after the terminal observation.
4. For exact replay, construct a framework adapter that runs the existing graph with the provided
   `DependencyAdapter` instead of live clients. Tool nodes call `invoke_recorded_tool` with the same
   deterministic sanitizer and receive no live callable; the replay engine remains unaware of the
   graph.
5. Keep regression specifications outside the capsule and developer-reviewed.

The supported external integration surface is importable from the package root:
`CaptureSession`, `DependencyAdapter`, and `invoke_recorded_tool`. Generic tool capture requires
the standard scanner. Tool results that need transformation cannot produce a capsule in v0.5; no
result-sanitizer API is available.

Do not copy application code, credentials, `.env` data, or provider configuration into TraceForge.
The controlled implementation in `traceforge.integrations.langgraph_weather` demonstrates the
in-repository adapter seam. The separate Agentic-chatbot integration additionally proves one real
package/API consumer with application-owned message codecs and dependency facade; it does not
broaden the core contract or claim arbitrary LangGraph support.
