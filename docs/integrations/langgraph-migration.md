# LangGraph Migration Guide

TraceForge's core package does not import LangGraph. Install the optional integration with `pip install "traceforge-replay[langgraph]"`.

For a future Agentic-chatbot integration branch, keep application ownership in that repository and make only these boundary changes:

1. Create a `CaptureSession` when a graph run begins, using sanitized run/application metadata. Use Replay Capsule `0.2.0` when the run records a generic tool dependency.
2. Wrap the existing injected model and HTTP clients with `record_model` and `record_http`. Wrap application tools with `record_tool`, and supply an application-owned deterministic argument sanitizer when default scanning would alter request identity. Keep provider-specific clients outside TraceForge core.
3. Record relevant node transitions with `record_event`, then call `finish` and `seal_capsule` after the terminal observation.
4. For exact replay, construct a framework adapter that runs the existing graph with the provided `DependencyAdapter` instead of live clients. Tool nodes call `invoke_recorded_tool` with the same deterministic sanitizer and receive no live callable.
5. Keep regression specifications outside the capsule and developer-reviewed.

The supported external integration surface is importable from the package root:
`CaptureSession`, `DependencyAdapter`, and `invoke_recorded_tool`. Generic tool capture requires
the standard scanner. Tool results that need transformation cannot produce a capsule in v0.5; no
result-sanitizer API is available.

Do not copy application code, credentials, `.env` data, or provider configuration into TraceForge. The controlled implementation in `traceforge.integrations.langgraph_weather` demonstrates the adapter seam without depending on Agentic-chatbot.
