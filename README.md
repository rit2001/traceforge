# TraceForge

TraceForge captures a failed AI-agent execution, freezes its external dependencies, enables exact and forked replay, compares execution paths, and converts developer-approved expected behaviour into a regression test.

## Current Status

TraceForge is an experimental, replay-first developer-tool project. The current work is a feasibility spike, not a production system, hosted service, LangSmith replacement, generic observability dashboard, or automatic-fix platform.

Initial support is intentionally narrow:

- Python agents only.
- LangGraph and tool-calling agents first.
- Local-only execution.
- Unit and CI tests are fully offline by default.
- No real API calls in the initial test suite.
- No copied application code or secrets from client applications.

## Core Workflow

1. Capture a failed local AI-agent execution.
2. Build a Replay Capsule containing the inputs, agent graph metadata, prompts, model responses, tool calls, tool outputs, and relevant execution metadata.
3. Run exact replay to reproduce the captured path using frozen model and tool outputs.
4. Run fork replay to hold tool outputs fixed while re-running the model or prompt, either with an offline fake or recorded adapter for regression checks or with an explicitly configured live model for opt-in experiments.
5. Compare the original, exact replay, and fork replay paths.
6. Let the developer approve expected behaviour.
7. Export approved expectations as an offline regression test.

## Exact Replay Versus Fork Replay

Exact replay freezes model outputs and tool outputs. Its purpose is reproducibility: the same captured execution should be replayable without depending on live services.

Fork replay freezes tool outputs but runs the model or prompt again. Its purpose is controlled exploration: developers can see whether a prompt, graph, or model change would behave differently against the same external facts.

Offline fork replay uses fake or recorded model adapters and recorded tool responses. It can validate replay-engine mechanics, but it cannot prove that a new prompt improves real model behaviour. Live fork experiments use a real explicitly configured model with recorded tool outputs. They are opt-in, may consume API quota, and must never run silently in default CI.

Deterministic offline regression checks and probabilistic live evaluations are separate activities. Prompt-quality claims require measured live evaluation results.

## Explicit Non-Goals

- TraceForge does not guarantee automatic fixes.
- TraceForge does not claim to eliminate hallucinations.
- TraceForge is not a LangSmith replacement.
- TraceForge is not a generic observability dashboard.
- TraceForge is not starting with SaaS authentication, payments, team management, or hosted storage.
- TraceForge is not starting with Go, Kafka, Terraform, Kubernetes, ClickHouse, or other infrastructure-heavy components.
- TraceForge will not fabricate benchmarks, users, reliability claims, or production-readiness claims.

## Five-Day Feasibility Spike Status

The first milestone is a five-day feasibility spike around replaying a controlled local LangGraph weather-agent failure using the separate existing Agentic-chatbot repository as the system under test. A genuine production failure may be used later if one is explicitly supplied, but the initial fixture must not be described as a production incident. The spike must not copy application code or secrets from that repository, must not inspect or create `.env` files, and must prove the replay loop through offline tests before broader architecture work begins.

The spike is not complete yet. The project should not add production infrastructure or generalized platform features until the replay feasibility question has been measured.
