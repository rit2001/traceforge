# ADR-0009: Portable Structured Execution Diff

- Status: Accepted
- Date: 2026-10-02

## Context

TraceForge currently reports observation equality through the boolean
`deterministic_match`. It cannot explain which portable execution values differed, where they
differed, or which sections remained equal.

Replay Capsules `0.1.0` and `0.2.0` already contain immutable original observations, generic
ordered dependencies, portable events, terminal output, execution status, and portable errors.
Successful replay produces a new portable observation. A small runtime dependency transcript can
describe successfully consumed generic replay dependencies without changing capsule evidence.

ADR-0008 requires diff semantics to remain independent of LangGraph, LangChain, CrewAI, and every
other framework. Framework-native values may be translated into portable JSON by an adapter, but
the core cannot interpret graph nodes, messages, callbacks, routing, or framework lifecycle
semantics.

## Decision

TraceForge will introduce a derived, framework-neutral `ExecutionDiff` contract with format
version `0.1.0`. This ADR defines that future contract; it does not itself implement the diff.

The diff compares:

- original and replay execution status and portable error records;
- recorded and replay dependency streams;
- original and replay portable event streams; and
- original and replay terminal output.

The comparator never modifies a Replay Capsule or any supplied input. Replay Capsule `0.1.0` and
`0.2.0` remain unchanged. No Replay Capsule schema evolution is required.

## Inputs

The comparison consumes:

- `original_observation` from validated immutable capsule evidence;
- a validated portable `replay_observation` produced by replay;
- the capsule's globally ordered recorded dependencies; and
- an ordered replay-runtime dependency transcript.

The replay transcript contains only generic JSON-compatible fields needed for comparison:
`sequence`, `kind`, `operation`, `request`, and `outcome`. It contains no framework objects,
callables, graph state, or exception instances.

Unsupported Python values are rejected. They are never coerced or stringified to make comparison
succeed.

## Canonical JSON

TraceForge uses its existing RFC 8785 JSON Canonicalization Scheme implementation for:

- validating that diff inputs use supported JSON values;
- exact-record signatures;
- canonical multiset comparison;
- deterministic object-member traversal; and
- canonical serialization of an `ExecutionDiff` document.

RFC 8785 property ordering by UTF-16 code units and its supported number constraints are
authoritative. Non-finite numbers, integers outside the interoperable IEEE-754 range, invalid
Unicode, non-string object keys, and unsupported Python types are rejected by the existing
canonicalization boundary.

TraceForge does not introduce a second canonical JSON definition. Fixed ordering among diff
sections is array/presentation ordering, not an alternative object-property canonicalization
policy.

## Result Contract

`ExecutionDiff` is a versioned, JSON-compatible derived result. It contains:

- `format_version`;
- an overall `matches` summary;
- the canonicalization, path, and diagnostic-field policy;
- match status and difference count for each section;
- one first-divergence location per section; and
- a deterministically ordered list of structured differences.

Every difference contains:

- `section`;
- a stable machine-readable `code`;
- `path`;
- `expected_path`;
- `actual_path`;
- a detached expected-value snapshot; and
- a detached actual-value snapshot.

Each value snapshot has `present`, `type`, and `value`. The comparison-only type `missing` is
distinct from JSON `null`.

Human-readable prose may be derived later, but it is not the source of truth.

## Path Contract

Difference locations use RFC 6901 JSON Pointer under this fixed logical namespace:

- `/execution_status`
- `/error`
- `/dependencies`
- `/events`
- `/output`

There is no `/observation` prefix. Object-member names escape `~` as `~0` and `/` as `~1`.
Array indices are zero-based decimal indices.

Paths are side-specific:

- For the same-index value change, `expected_path` and `actual_path` point to their respective
  values, and `path` uses the expected path.
- For paired records at different indices, `expected_path` uses the original index,
  `actual_path` uses the replay index, and `path` uses the expected path.
- For a missing value, `expected_path` points to the existing original value, `actual_path` is
  `null`, and `path` equals `expected_path`.
- For an extra value, `expected_path` is `null`, `actual_path` points to the existing replay value,
  and `path` equals `actual_path`.
- For a pure reorder or array-length difference, both side paths and `path` identify the
  containing collection.

A null side path means no value exists on that side. The comparator does not use a pointer to a
nonexistent value as if it were an existing location.

## Recursive JSON Comparison

The supported JSON types are object, array, string, number, boolean, and null.

- A type change produces one `type_changed` difference at that path and stops descent there.
- Objects compare the union of keys in RFC 8785 property order.
- Arrays compare their ordered items and report length plus missing or extra items.
- Scalars produce `value_changed` when unequal under the defined JSON semantics.
- Booleans are distinct from numbers.
- JSON numbers follow RFC 8785 constraints and canonical number semantics.

Diagnostic fields retain the existing observation-comparison policy. The policy is disclosed in
the result and includes `duration_ms`, `recorded_at`, `timestamp`, `started_at`, and `finished_at`.
Dependency-record `duration_ms` is diagnostic and is not part of dependency identity or outcome
comparison.

## Ordered Dependency Comparison

Dependencies compare the generic content projection:

- `kind`;
- `operation`;
- `request`; and
- `outcome`.

`dependency_id`, `sequence`, `request_fingerprint`, and `duration_ms` are excluded from alignment
identity. The fingerprint is derived and validated separately. Sequence remains a structural
position: each stream must be contiguous and agree with its one-based array order.

Dependency comparison can report:

- missing or extra calls;
- pure reordering;
- changed kind or operation;
- recursively changed request values;
- returned-versus-errored outcome changes;
- recursively changed returned values; and
- recursively changed portable error `type`, `message`, or `data`.

## Ordered Event Comparison

Events compare only their generic content projection:

- `kind`;
- `name`; and
- `data`.

`event_id` and `sequence` are excluded from alignment identity. Sequence remains a structural
position and must be contiguous and agree with one-based array order.

The core treats event kind, name, and data as opaque portable JSON. Values such as `chat_node` and
`ToolMessage` receive no LangGraph, LangChain, message, node, or tool semantics.

Event comparison can report missing or extra events, pure reordering, changed kind or name, and
recursive data differences.

## Conservative Sequence Alignment

Dependencies and events use the same conservative alignment procedure:

1. Validate every comparison value through TraceForge's RFC 8785 canonicalization.
2. Validate that declared sequences are contiguous and agree with array order.
3. Canonicalize every complete comparison projection.
4. If the ordered canonical projections are identical, the stream matches.
5. If the complete canonical multisets are equal but their order differs, report exactly one pure
   `dependency_reordered` or `event_reordered` difference. Do not additionally describe those
   records as changed. Identical duplicate records are indistinguishable, so exchanging them is
   not an observable reorder.
6. Otherwise, calculate a deterministic longest common subsequence using exact canonical-record
   equality.
7. Resolve each unmatched gap conservatively:
   - With no expected records and one or more actual records, report every actual record as extra.
   - With one or more expected records and no actual records, report every expected record as
     missing.
   - With exactly one expected and one actual record, compare them as one changed record.
   - With multiple unmatched records on either side, pair dependency records only when the generic
     `(kind, operation)` anchor occurs exactly once in that expected gap and exactly once in that
     actual gap.
   - With multiple unmatched records on either side, pair event records only when the generic
     `(kind, name)` anchor occurs exactly once in that expected gap and exactly once in that actual
     gap.
   - A uniquely anchored pair may occupy different indices, but the result does not call it moved.
   - Report every remaining expected record as missing and every remaining actual record as extra.
   - Do not pair leftover records merely because only one record remains on each side after unique
     anchor processing.
8. When LCS candidate lengths are equal, prefer advancing the expected side before the actual
   side.
9. Process gaps in LCS order. Within a gap, report changed pairs ordered by expected and then
   actual index, followed by missing records in expected-index order and extra records in
   actual-index order.

This procedure permits exact-record matching, deterministic LCS alignment, complete-multiset pure
reorder detection, and unique generic anchors. It does not invent application or framework
identity, arbitrarily pair unmatched records, or claim an unproven move/change relationship.

## Execution Status and Errors

The comparator handles the portable execution statuses `completed`, `errored`, and `cancelled`.

- Completed versus completed compares events and terminal output.
- Completed versus errored, or errored versus completed, reports status, output, and error
  differences separately.
- Errored versus errored recursively compares portable error `type`, `message`, and `data`.
- Cancelled combinations follow the same status-first rule.

Diffing reads portable error records only. Evidence never selects an exception class to import or
construct.

A subject observation with `execution_status: "errored"` is distinct from a replay technical
failure. If exact replay raises before producing a valid replay observation, no completed
`ExecutionDiff` exists.

## First Divergence

TraceForge reports separate first divergences for:

- execution status and error;
- dependencies;
- events; and
- terminal output.

Dependencies and events have independent sequences, and terminal output has no sequence shared
with either collection. TraceForge therefore does not invent a global chronology or claim one
globally first divergence.

The combined difference list uses the fixed presentation order execution, dependencies, events,
then terminal output. That order provides deterministic rendering only; it is not execution
chronology.

## Exact Replay Dependency Transcript

During successful exact replay, each runtime dependency transcript entry records:

- the actual generic request supplied to the recorded-dependency boundary;
- the matched sequence, kind, and operation; and
- the recorded outcome injected by TraceForge.

The outcome is not an independently executed provider outcome. Successful exact replay therefore
has matching dependency outcomes by construction. Kind, operation, request identity, and ordering
also match because exact replay enforces them, and all fixtures must be consumed.

A successfully consumed errored outcome remains part of the transcript even if application-side
logic subsequently raises or handles an approved replay exception.

Dependency mismatches, missing calls, extra calls, and reordered calls retain their existing typed,
fail-closed replay failures. They do not become completed replay results, and exact replay never
falls back to a live dependency.

The generic comparator may later compare independently produced fork or live transcripts, where
outcomes can differ. This ADR adds no fork or live replay behavior.

## Immutability and Aliasing

`ExecutionDiff` is an alias-isolated derived value object.

- The comparator never mutates an input.
- The result retains no mutable alias to caller-owned dictionaries or lists.
- Expected and actual snapshots are detached before entering the result.
- Public result attributes cannot be rebound.
- Internal nested containers are not exposed directly.
- `to_dict()` or equivalent serialization returns a newly allocated document on every call.
- Mutating an exported document cannot mutate an input, mutate the internal result, or affect a
  later export.
- Canonical serialization operates on a fresh detached document.

A frozen dataclass alone is not sufficient if it exposes nested mutable dictionaries or lists.
The implementation may use private detached storage and copy-on-export; it does not require a
general persistent-collection framework.

## Separation of Concerns

Replay technical status answers whether replay validated, executed, consumed its fixtures, and
completed correctly. `ExecutionDiff` answers what changed in the portable execution evidence.
`RegressionResult` answers whether replay satisfied separately maintained, developer-authored
expectations.

The three concerns are not reducible to one another. A technical replay failure may prevent a
completed ExecutionDiff from being produced.

A technically successful replay may have a non-matching diff. A non-matching diff may still pass a
regression specification whose approved expectations are unaffected. A matching diff may fail a
regression specification that expects behavior different from the captured observation.
Regression expectations remain outside capsule evidence and outside the diff result.

## Compatibility

- Replay Capsule `0.1.0` remains unchanged and supported.
- Replay Capsule `0.2.0` remains unchanged and supported.
- No Replay Capsule schema is changed or added by this decision.
- Exact replay validation, ordering, request matching, fixture consumption, network blocking, and
  fail-closed behavior remain unchanged.
- Regression specifications and evaluation semantics remain unchanged.
- Existing `deterministic_match` remains available with its current meaning for compatibility.
- The structured diff is an additive, separately versioned derived result.
- Storage and transport semantics remain unchanged.

## Framework Boundary

Core diff code imports and interprets no framework types or lifecycle concepts. Framework-specific
translation and presentation remain in adapters or presentation layers under ADR-0008.

A future framework should require a thin adapter and adapter-focused tests. It must not require
changes to Replay Capsule evidence, replay semantics, the structured diff engine, regression,
storage, or transport.

## Consequences

- Engineers can inspect deterministic, machine-readable differences rather than one boolean.
- Existing capsule evidence needs no rewrite or migration.
- The core can compare status, errors, dependencies, events, and terminal output without learning
  framework semantics.
- Successful exact replay dependency outcomes match by construction.
- Ambiguous sequence changes are reported conservatively as missing and extra records.
- Framework-specific renderings can be derived without changing the core result.
- Large executions may produce large complete diff results. Any display truncation belongs to a
  presentation layer and cannot change the core source of truth.
- A derived diff may duplicate sensitive portable values, so it must not be persisted
  automatically and requires the same review discipline as its inputs.

## Alternatives Rejected

### Define UTF-8 Object-Key Ordering

Rejected. TraceForge already uses RFC 8785, whose object-property ordering is based on UTF-16 code
units. A second subtly different canonical JSON definition would undermine determinism.

### Embed Diff Data in Replay Capsules

Rejected. A diff is derived from original evidence and replay/runtime artifacts. Embedding it would
mutate or version immutable evidence unnecessarily.

### Interpret Framework Nodes or Messages in Core

Rejected under ADR-0008. Strings and portable values remain opaque to the core.

### Pair Every Unmatched Expected and Actual Record

Rejected. Positional proximity does not prove semantic identity. Only a one-to-one gap or a unique
generic anchor can justify changed-record comparison.

### Report Reorder from Partial Similarity

Rejected. Pure reorder is reported only when the complete canonical comparison-record multisets
match.

### Report One Global First Divergence

Rejected. The evidence model does not provide a shared chronology across dependencies, events,
and terminal state.

### Turn Exact Replay Mismatches into Completed Diffs

Rejected. That would weaken the existing fail-closed replay contract and conflate technical replay
failure with behavioral comparison.

### Stringify Unsupported Python Objects

Rejected. Stringification hides type and portability failures and can create false equality.
