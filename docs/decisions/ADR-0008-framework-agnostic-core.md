# ADR-0008: Framework-Agnostic Evidence and Replay Core

- Status: Accepted
- Date: 2026-10-02

## Context

The v0.5.0 Real Agent Capture milestone uses LangGraph as the first real integration proof. That
choice can accidentally turn one framework's graph, node, state, and callback model into
TraceForge's evidence and replay model. Doing so would make later framework support require core
schema or replay changes instead of a new adapter.

TraceForge already has generic evidence concepts: invocation input, ordered dependency outcomes,
ordered execution events, terminal observations, validation, sealing, exact replay, and separate
regression expectations. The LangGraph proof must exercise those concepts without redefining them.

## Decision

TraceForge's capture core, Replay Capsule schemas and contracts, dependency contract, sealing,
validation, replay engine, regression model, and future core diff model remain framework-agnostic.
They must not depend on LangGraph types, `StateGraph`, node semantics, callback contracts, graph
state rules, or other LangGraph-specific assumptions.

Framework-specific translation belongs behind an integration/adapter boundary. A LangGraph
adapter may observe framework-native callbacks or state and translate them into TraceForge's
generic invocation, dependency, event, and observation contracts. It may also provide an
integration-specific presentation outside the core diff/regression model. It must not add
LangGraph meaning to generic fields or make sealing, validation, replay, regression, or diff logic
interpret LangGraph concepts.

The `subject.framework` value is descriptive provenance only. Generic internal events retain the
portable `kind`, `name`, and sanitized `data` envelope; no event kind or payload shape becomes a
core LangGraph contract merely because the first adapter emits it.

A future framework integration should require a new thin adapter plus adapter-focused tests. It
must not require changes to TraceForge's evidence or replay semantics. If LangGraph's API shape
appears to require a core change solely for LangGraph, implementation stops and the adapter
boundary is reconsidered. A core change may proceed only when justified as a framework-neutral
TraceForge capability, with the normal versioning and ADR requirements.

## Consequences

- LangGraph remains the first integration proof, not the domain model.
- Core packages must not import LangGraph or expose LangGraph-native types.
- Replay Capsules may identify LangGraph as provenance but cannot encode mandatory graph, node,
  state, or callback semantics.
- Core regression assertions and future structured diffs operate on portable observations,
  events, dependencies, and outputs. Framework-specific views remain adapter-side derivations.
- Adapter tests must prove both the translation and the absence of a required LangGraph import in
  the core package.
- Supporting another framework should add a thin adapter and tests rather than modify evidence or
  replay semantics.

## Alternatives Considered

### Make LangGraph the Core Execution Model

Rejected. It would make a framework's graph and callback lifecycle part of TraceForge's durable
contract and force unrelated frameworks through LangGraph-shaped abstractions.

### Add LangGraph Fields Now and Generalize Later

Rejected. Sealed evidence and regression contracts are expensive to reinterpret safely. Deferring
the boundary would create migration pressure precisely where TraceForge requires stable semantics.

### Keep the Boundary as an Informal Convention

Rejected. The active milestone directly exercises LangGraph, so an undocumented convention is too
easy to violate across capture, schema, replay, regression, and diff work.
