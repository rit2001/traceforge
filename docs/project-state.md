# Project State

Last verified date: 2026-07-17.

## Current Phase

TraceForge is in documentation and feasibility definition. The repository is not yet an implementation project.

## Current Milestone

Five-day weather replay feasibility spike.

The milestone uses a controlled local LangGraph/OpenWeather failure from Agentic-chatbot as the system under test unless a genuine production failure is later supplied.

## Repository Status

Documentation scaffold only. Implementation has not started.

No source-code directories, package metadata, dependency files, Docker files, tests, fixtures, or service infrastructure have been added.

## Confirmed Decisions

- TraceForge is replay-first, not a broad LangSmith clone.
- First support is Python, LangGraph, and tool-calling agents.
- Initial execution is local-only.
- Exact replay freezes recorded model outputs and recorded tool outputs.
- Offline fork replay uses recorded tool outputs with fake or recorded model adapters.
- Live fork experiments are opt-in, may consume API quota, and never run in default CI silently.
- AI-generated assertions require developer approval before becoming regression tests.
- TraceForge and Agentic-chatbot remain separate repositories.
- Agentic-chatbot integration eventually happens by installing a local TraceForge Python package/API on a dedicated integration branch.
- Sanitized capsule fixtures may be stored in TraceForge only after review.

## Current Assumptions

- The first useful capsule can be file-based and local.
- A controlled weather grounding failure is enough to test the replay loop.
- Fake-model tests are sufficient for replay-engine mechanics but not for prompt-quality claims.
- Prompt-quality claims require measured live evaluation results.

## Known Blockers and Open Questions

- Replay Capsule schema is not defined.
- Capture boundary inside Agentic-chatbot is not defined.
- Sanitization review rules for capsule fixtures are not defined.
- The exact offline fake or recorded model adapter shape is not defined.
- The package/API surface for future Agentic-chatbot integration is not defined.

## Deliberately Postponed Technologies

Go, Kafka, Terraform, Kubernetes, ClickHouse, distributed storage, microservices, SaaS authentication, and payment systems are postponed until replay evidence shows they are needed.

## Exact Next Approved Task

Define the controlled Weather Grounding Capsule scenario and its required captured fields. Do not implement source code until that scenario and acceptance criteria are approved.

## Milestone-Boundary Checklist

Update this file when:

- A milestone is completed.
- The approved next task changes.
- A blocker is resolved or a new blocker is found.
- A significant assumption becomes a decision.
- A postponed technology is reconsidered.
