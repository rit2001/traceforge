# LangGraph Migration Guide

TraceForge's core package does not import LangGraph. Install the optional integration with `pip install "traceforge-replay[langgraph]"`.

For a future Agentic-chatbot integration branch, keep application ownership in that repository and make only these boundary changes:

1. Create a `CaptureSession` when a graph run begins, using sanitized run/application metadata.
2. Wrap the existing injected model and tool clients with `record_model` and `record_http`; keep provider-specific clients outside TraceForge core.
3. Record relevant node transitions with `record_event`, then call `finish` and `seal_capsule` after the terminal observation.
4. For exact replay, construct a framework adapter that runs the existing graph with the provided `DependencyAdapter` instead of live clients.
5. Keep regression specifications outside the capsule and developer-reviewed.

Do not copy application code, credentials, `.env` data, or provider configuration into TraceForge. The controlled implementation in `traceforge.integrations.langgraph_weather` demonstrates the adapter seam without depending on Agentic-chatbot.
