# ADR-0001: Replay-First Product

Status: Accepted

Date: 2026-07-17

## Context

AI-agent developer tools often expand quickly into broad tracing, monitoring, hosted dashboards, evaluation suites, collaboration features, and production observability. TraceForge is starting from a narrower product problem: a developer has a failed local agent execution and needs to reproduce, fork, compare, and lock in the expected behaviour as a regression test.

The first client application is a separate existing repository, Agentic-chatbot. It must remain separate. TraceForge must not copy its application code or secrets and must not inspect `.env` files.

## Decision

TraceForge will be a replay-first developer tool. The initial product surface is:

- Capture a failed Python LangGraph or tool-calling agent execution.
- Store the run as a local Replay Capsule.
- Support exact replay with frozen model and tool outputs.
- Support fork replay with frozen tool outputs and fresh model or prompt execution.
- Diff execution paths and relevant outputs.
- Export developer-approved expected behaviour as offline regression tests.

The project will not add source-code directories, package metadata, infrastructure, or production platform components until the replay feasibility spike has enough evidence to justify implementation.

## Why a Broad LangSmith Clone Was Rejected

A broad LangSmith clone would shift the project toward hosted trace storage, dashboards, dataset management, evaluations, collaboration, authentication, billing, and production observability. Those features do not answer the first product risk: whether replaying and forking a failed agent execution creates enough developer value.

Building a broad clone early would also increase scope, require infrastructure decisions too soon, and make it easier to rely on generic observability language instead of proving the replay loop.

## Consequences

- The first milestone is intentionally narrow.
- Local Replay Capsules are more important than hosted storage.
- Offline tests are more important than dashboards.
- Python and LangGraph support comes before language or framework breadth.
- Redaction and secret boundaries must be designed early.
- Infrastructure choices are delayed until measured need exists.
- Product claims must remain modest until evidence exists.

## Alternatives Considered

### Generic Observability Dashboard

Rejected for the initial milestone. Dashboards can display failures, but they do not by themselves freeze dependencies, replay paths, or export approved regression tests.

### Hosted Trace Platform

Rejected for the initial milestone. Hosting introduces authentication, storage, billing, privacy, and deployment concerns before the local replay value is proven.

### Evaluation Suite First

Rejected for the initial milestone. Evaluations are useful, but TraceForge starts from real failed executions and developer-approved regression tests rather than broad benchmark-style scoring.

### Automatic Fix Agent

Rejected. TraceForge may help developers understand and test fixes, but it does not guarantee automatic repair.
