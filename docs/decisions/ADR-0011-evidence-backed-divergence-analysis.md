# ADR-0011: Evidence-Backed Divergence Analysis

- Status: Accepted
- Date: 2026-10-04

## Context

ADR-0009 introduced a deterministic, framework-neutral `ExecutionDiff` that identifies portable
differences in four independent evidence domains: execution status/error, dependencies, events,
and terminal output. It intentionally reports one first divergence per domain because those
domains do not share one proven global chronology.

The complete diff is suitable for forensic inspection, but it does not provide a compact answer
to which domains matched, which diverged, and what bounded exact-replay context is already proven.
That summary must not become a second comparison engine, a causal model, or speculative prose.

## Decision

TraceForge will add a derived, framework-neutral `DivergenceAnalysis` contract with format version
`0.1.0`. It is runtime data derived exclusively from a completed `ExecutionDiff`; it never mutates
Replay Capsule evidence and is not persisted automatically.

`DivergenceAnalysis` does not replace `ExecutionDiff`, which remains the structured comparison
source of truth. It does not replace `RegressionResult`, which continues to evaluate separately
maintained developer expectations. Human-readable prose is presentation derived from the
structured analysis and is never authoritative data.

The originally proposed pure API was:

```python
analyze_divergence(execution_diff, *, exact_replay_completed=False)
```

### Adversarial Review Correction — 2026-10-04

The caller-controlled `exact_replay_completed` boolean above was rejected before release because
it would let a standalone public caller forge exact-replay provenance. The accepted public API is
therefore `analyze_divergence(execution_diff)`, which always reports standalone context. A separate
non-exported orchestration path attaches exact-replay context only after validation, subject
execution, ordered dependency matching, complete fixture consumption, portable observation
validation, and `ExecutionDiff` construction have succeeded. The package root does not export that
path, and no public API accepts a completion boolean.

Neither path recomputes observations, dependencies, events, or output. Both read only the existing
`ExecutionDiff.matches`, `sections`, and `first_divergences` values retained in trusted compact
metadata. Unknown versions, unknown fields, malformed metadata, inconsistent summaries, and
domain-inconsistent first paths fail closed.

## Result Contract

`DivergenceAnalysis.to_dict()` returns a new JSON-compatible document with exactly these fields:

- `format_version`: `"0.1.0"`;
- `matches`: copied from `ExecutionDiff.matches`;
- `domains`: the fixed `execution`, `dependencies`, `events`, and `terminal` objects;
- `evidence_context`: bounded facts about this analysis runtime;
- `findings`: stable machine-readable finding codes; and
- `limitations`: stable machine-readable limitation codes.

Each domain contains:

- `matches`, copied from the corresponding diff section;
- `difference_count`, copied from the corresponding diff section; and
- `first_path`, copied exactly from the corresponding `ExecutionDiff.first_divergences` value.

There is deliberately no `global_first_divergence`, `first_divergence`, ranked-domain, causal, or
root-cause field.

`evidence_context` contains:

- `replay_completed_technically`: true only when the exact-replay orchestrator produced this
  analysis after a technically successful exact replay; and
- `recorded_dependencies_reproduced`: true only when that exact replay completed technically
  and the dependency domain matches.

For successful exact replay, a matching dependency domain proves that recorded kind, operation,
request identity, ordering, fixture consumption, and injected recorded outcomes were reproduced.
It does not prove anything about what an external provider would return now or whether the
external world caused a behavioral result.

## Finding Codes

Version `0.1.0` supports these findings in fixed deterministic order:

1. `recorded_dependencies_reproduced`, when the bounded exact-replay context above is true;
2. `no_semantic_divergence`, when `ExecutionDiff.matches` is true;
3. `execution_diverged`, when the execution domain differs;
4. `dependency_stream_diverged`, when the dependency domain differs;
5. `event_stream_diverged`, when the event domain differs; and
6. `terminal_output_diverged`, when the terminal domain differs.

`no_semantic_divergence` means only that no difference exists under the versioned portable
`ExecutionDiff` policy. It is not a claim of universal application equivalence.

## Limitation Codes

Every `0.1.0` analysis states:

- `no_global_chronology`;
- `no_root_cause_claim`; and
- `no_cross_domain_causality`.

These are contract boundaries, not optional warnings. Presentation may explain them but cannot
weaken them.

## Successful and Failed Replay

`ReplayResult` gains an additive optional final `divergence_analysis` field. A technically
successful exact replay sets it after constructing `ExecutionDiff`. Existing positional
constructor behavior remains valid, and existing fields retain their meanings.

If exact replay fails because of a dependency mismatch, missing or unexpected dependency,
validation failure, blocked live dependency, runner failure, or any other technical failure, it
still fails closed. No completed `ExecutionDiff` or `DivergenceAnalysis` is fabricated. A future
technical-failure analysis would require a separate versioned contract and decision.

A standalone `ExecutionDiff` can be analyzed only through the public provenance-free API.
Dependency differences are represented normally, while both exact-replay context booleans remain
false. This prevents a generic or future fork/live comparison from pretending that exact replay
succeeded.

## Immutability and Serialization

`DivergenceAnalysis` is an alias-isolated immutable public value. It retains one private canonical
RFC 8785 document, exposes no nested mutable state, and returns a newly allocated document from
every `to_dict()` call. Mutating an exported document cannot change the analysis, the source
`ExecutionDiff`, or a later export. Canonical serialization is available from the same retained
bytes and introduces no second JSON policy.

## Framework Boundary

The analysis understands only the four portable `ExecutionDiff` domains. It imports and
interprets no framework type, node, message, state, callback, planner, supervisor, or lifecycle
concept. Framework adapters may later map native evidence into portable events or evidence
locations, but core analysis remains unchanged under ADR-0008.

## Future Compatibility

A later version may add evidence locations such as `trace_id`, `span_id`, `parent_span_id`,
`component_id`, or a verification relationship. Such fields may improve navigation or, under a
separately designed causal evidence contract, support stronger attribution. They do not change
today's lack of a shared chronology or causal proof.

## Consequences

- Developers receive a compact deterministic map of matched and diverged evidence domains.
- Every diverged domain points to its own first proven path from `ExecutionDiff`.
- Exact replay can truthfully report reproduction of its recorded dependency fixtures and their
  injected outcomes; it makes no claim that an external dependency or its current state was
  reproduced.
- Full structured differences and regression results remain separate and available.
- The Workbench can render useful guidance without an LLM or heuristic explanation.
- TraceForge still refuses to identify a global earliest divergence, root cause, causal chain, or
  responsible model/tool from this evidence.

## Alternatives Rejected

### Report One Global First Divergence

Rejected by ADR-0009 and preserved here. Dependencies, events, execution state, and terminal
output do not share one proven global chronology. Fixed rendering order is not temporal order.

### Generate a Root-Cause Explanation

Rejected. A difference location proves an observed mismatch, not why another domain changed.
Neither rules nor an LLM can upgrade absent causal evidence into proof.

### Recompare Values in the Analysis Layer

Rejected. A second comparator could drift from ADR-0009 alignment, diagnostic, and path semantics.
`ExecutionDiff` remains the sole comparison source of truth.

### Produce Analysis for Technical Replay Failures

Rejected. Turning dependency or execution failures into a completed behavioral analysis would
weaken fail-closed exact replay and conflate technical failure with portable divergence.

### Store Analysis in Replay Capsules or Replay History

Rejected. The analysis is derived runtime data. This issue introduces no schema change, storage
migration, or persistence contract.
