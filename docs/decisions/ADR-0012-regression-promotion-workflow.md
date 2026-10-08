# ADR-0012: Regression Promotion Workflow

- Status: Accepted
- Date: 2026-10-06

## Context

TraceForge already preserves a historical execution as an immutable Replay Capsule, replays its
recorded dependencies offline, derives `ExecutionDiff` and `DivergenceAnalysis`, evaluates a
separate developer-authored regression specification, and exports that specification as pytest.
The missing workflow is the deliberate transition from a reviewed repaired replay to a durable
regression guard.

That transition must not reinterpret the original run. Historical evidence answers what happened;
a regression specification answers what a developer now expects. A technically successful replay,
a matching `ExecutionDiff`, or a passing `RegressionResult` cannot approve or rewrite an
expectation automatically.

## Decision

Regression promotion is the explicit creation of a new `RegressionSpec 0.1.0` document from
developer-selected expectations that pass against a supplied, technically completed replay result.
The existing regression specification is the only durable promotion artifact. TraceForge will not
add a second wrapper containing copied replay output, runner metadata, diff data, or analysis data.

The public workflow API is:

```python
promote_regression(
    replay_result,
    assertions,
    *,
    developer_approved: bool,
)
```

`developer_approved` is keyword-only and has no default. The function rejects every value other
than the boolean `True`. Calling code must therefore represent a deliberate approval action.

The returned document has exactly the existing contract:

```json
{
  "version": "0.1.0",
  "assertions": [
    {"path": "output.answer", "operator": "equals", "expected": "reviewed value"}
  ]
}
```

Promotion reuses `evaluate_regression()` as the assertion validator and evaluator. It adds no
operator, path language, wildcard, matcher, or inference rule. Version `0.1.0` continues to support
only the existing `equals` and `contains` operators over the existing dot-separated dictionary
paths.

## Trust Boundary

The Replay Capsule is captured historical evidence and remains immutable. Promotion never writes
to it, changes its integrity scope, or embeds expectations inside it.

The promoted `RegressionSpec` is a mutable, developer-authored source artifact. Its assertions are
review decisions, not captured facts. Source control review, not capsule integrity, records changes
to that artifact.

`ExecutionDiff` remains a derived comparison, `DivergenceAnalysis` remains a derived bounded
interpretation, and `RegressionResult` remains one evaluation result. None becomes an expectation
and none is modified by promotion.

The approval flag records caller intent only. It is not evidence of authorship, identity, code
review, or organizational authorization. TraceForge remains local and unauthenticated.

`ReplayResult` is a public constructible Python value. The public `promote_regression()` function
therefore trusts the caller-supplied result and does not prove that `replay_exact()` created it. Its
truthful guarantee is narrower: the caller explicitly approved assertions that validate and pass
against the supplied completed result. Workbench establishes a stronger bounded context by
performing `replay_exact()` on the server during every promotion request using the currently
submitted validated capsule and the startup-registered trusted runner. It ignores browser-supplied
replay status, diff, analysis, comparison, or result values.

## Promotion Eligibility

A promotion request is accepted only when:

- its source is a `ReplayResult` whose technical status is `completed`;
- the supplied result contains non-null `ExecutionDiff` and `DivergenceAnalysis` values;
- the developer supplies a non-empty assertion array explicitly;
- assertion values are strict JSON with finite numbers and string object keys, and exact duplicate
  assertions are rejected;
- every assertion uses the existing regression contract;
- every selected path exists in the replay observation; and
- the resulting specification passes against that supplied replay observation.

Promotion does not require `deterministic_match` to be true. A repaired replay is expected to be
able to differ from the historical failure while satisfying the newly approved expectation.
Promotion also does not treat an earlier `RegressionResult` as approval: an existing result may
help the developer review behavior, but the newly selected assertions are validated independently.

No assertion is inferred from terminal output, diff snapshots, divergence paths, event data,
dependency data, or unrelated fields. TraceForge never snapshots the entire replay output by
default.

## Export and CI

The promoted specification follows the existing pytest export path. `export_pytest()` remains the
filesystem-writing boundary and keeps its fail-if-present default; only trusted local caller code
can opt into replacement with `force=True`. The generated test loads the sealed capsule and
separate specification, loads trusted local runner code, calls `replay_exact()`, and fails pytest
when the approved regression result fails.

The generated test inherits exact replay's validation, ordered fixture matching, complete fixture
consumption, process-wide network guard, and fail-closed behavior. It is suitable for generic
offline CI when the reviewed capsule, specification, runner code, and TraceForge package are
available. This decision adds no provider integration, GitHub App, bot, hosted service, or live
dependency behavior.

## Workbench Workflow

After a technically completed replay, Workbench may offer **Promote to regression** whether the
replay had no existing specification, passed an existing specification, or failed an existing
specification. The UI must state that historical evidence and approved expectations are different.

The developer must add each assertion, choose an existing operator, enter an expected JSON value,
and confirm that the replay and expectations were reviewed. Nothing is preselected from the replay
output. Generating artifacts performs another explicit exact replay with the current submitted
capsule and startup-registered runner so the server can apply the domain promotion contract without
trusting a browser-supplied replay result.

Workbench returns one deterministic in-memory ZIP bundle containing the unchanged submitted sealed
capsule document, promoted specification, and pytest source under fixed path-safe internal names.
The bundle filename includes a digest of the complete bundle, so different artifact sets do not
collide under one advertised filename. This prevents independent browser rename behavior from
pairing a new test with stale separately downloaded evidence or expectations. HTTP input cannot
select a server path, filename, archive entry, output directory, runner import, or overwrite
target. The pytest source is rendered by the same implementation used by `export_pytest()`;
Workbench does not create a second exporter or write a server file.

## Consequences

- The product workflow becomes Capture → Replay → Understand → Promote → CI.
- Historical evidence remains stable while reviewed expectations can evolve in source control.
- A repaired replay with a non-matching historical observation can become a regression guard.
- Promotion is deterministic for the same replay result and selected assertions.
- Developers must intentionally choose the regression surface; broad output snapshots are not a
  convenience default.
- Browser export cannot write arbitrary server files or overwrite an existing local artifact.
- First-time expectations and intentional replacements for a failed old specification can be
  promoted without circular gating.
- Trusted runners remain local code with process authority; the socket guard is not an operating-
  system sandbox and cannot block every local side effect.

## Alternatives Rejected

### Add a `RegressionPromotion` durable wrapper

Rejected. Capsule digest, runner, diff, analysis, and approval metadata would duplicate inputs to
replay/export without changing assertion semantics. The existing specification is the durable
developer-owned artifact.

### Copy the complete replay output into expectations

Rejected. It would silently approve diagnostic or unrelated fields, create brittle tests, and blur
reviewed intent with a snapshot.

### Auto-accept a passing replay or diff

Rejected. Passing execution describes runtime behavior; it does not make a developer decision.

### Require deterministic equality with the historical run

Rejected. The intended repaired behavior may differ from the captured failure. Deterministic match
and approved correctness remain separate.

### Write browser-selected server paths

Rejected. The browser is not a trusted filesystem selector. It receives one server-named in-memory
bundle; trusted CLI callers retain the existing explicit output path and overwrite flag.

### Download capsule, specification, and pytest independently

Rejected. Browser collision renaming can change the three filenames independently while the pytest
source retains its internal references, silently mixing artifact generations. One content-addressed
bundle preserves a coherent source context without server persistence.

### Add provider-specific CI automation

Rejected. A normal offline pytest file is the portable CI contract for this milestone.
