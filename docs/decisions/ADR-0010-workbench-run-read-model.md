# ADR-0010: Workbench Original-Run Read Model

- Status: Accepted
- Date: 2026-10-03

## Context

TraceForge's existing local dashboard is centered on submitting evidence to exact replay and stores
only replay-attempt summaries in `replay_history`. The distributed capture path already persists
ordered operational capture state in SQLite and writes completed sealed Replay Capsules to the
filesystem. Workbench V1 needs a run catalog and execution-forensics view without confusing
operational capture metadata, immutable evidence, replay attempts, structured diffs, or regression
results.

The browser is an untrusted selector even though the Workbench process is trusted local tooling.
It cannot be allowed to choose filesystem paths or Python imports. Replay Capsule schemas and core
replay, diff, and regression semantics must remain unchanged and framework-agnostic.

## Decision

The Workbench's primary entity is an original captured run, identified by the assembly state's
`capture_id`. A small read-only Workbench catalog reads original-run operational metadata from the
assembly database and follows only capsule references already written there by the trusted
assembler.

Assembler versions in this milestone store an absolute service-local `capsule_path`. A trusted
Workbench startup may therefore also configure a capsule directory for a different local process
or mount namespace that shares the same persisted data. Resolution first preserves an existing
recorded path. When that path is absent in the Workbench environment, the catalog may fall back
only to `<configured capsule directory>/<capture_id>.json`. The capture ID must match the existing
portable identifier grammar, the resolved file must remain under the configured root, and symlink
or traversal escape is rejected. Browser input cannot select or override this root.

`replay_history` remains an append-only history of replay attempts. It is not an original-run
catalog and does not create an original run merely because a replay attempt exists.

The read model exposes immutable value objects rather than SQLite rows. It represents these states
explicitly:

- an incomplete capture with pending evidence;
- a completed capture whose capsule reference or file is missing;
- a completed capture whose capsule exists but fails loading or validation; and
- a completed capture with valid, integrity-verified evidence.

Evidence is called replayable only after the existing capsule validator succeeds and recorded tool
failure semantics pass the existing replayability preflight. Replayability does not imply that the
Workbench has a matching application runner registered.

Sealed capsule files remain the immutable evidence source. SQLite stores operational metadata and
a reference to evidence; the Workbench does not copy capsule content into SQLite, repair evidence,
or write presentation data back into a capsule. API responses expose capsule identity, schema
version, digest, and validation state when available, but do not expose filesystem paths.

A technically failed replay may have no `ExecutionDiff`. `ExecutionDiff` and `RegressionResult`
remain separate derived results and are never inferred by the frontend. The frontend renders
server-provided replay, diff, regression, and evidence states; it does not compute their semantics.

Run selection uses an opaque run ID in a fixed read-only API. Browser input cannot provide a
capsule path, module name, function name, or other code-loading reference. Trusted runner imports
remain a startup-only server configuration boundary.

Future trace, span, parent-child, component, verification-relationship, and multi-agent causal
fields may extend the Workbench read model additively. They must not redefine today's original run,
Replay Capsule evidence, replay attempt, diff, or regression result.

The Workbench remains localhost-first, unauthenticated, and intended for a trusted local process.
It is not a public or multi-tenant server.

## Consequences

- Original runs remain discoverable independently of replay attempts.
- Missing and invalid evidence cannot be presented as replayable.
- The UI can render real capture and evidence data without querying SQLite or opening files.
- Capsule integrity and schema handling continue to use one existing validation boundary.
- Framework-specific hierarchy remains adapter-side presentation; core storage and semantics stay
  generic.
- A missing assembly database yields an empty run catalog rather than synthetic runs.
- Every catalog request synchronously reads and validates each referenced capsule. Invalid or
  unreadable capsules are isolated to their own run state, but one large capsule or a large local
  catalog can delay the response; size bounds, pagination, and cached projections are deferred
  until measured need.
- Existing assembly databases containing container-local absolute paths remain readable from a
  host Workbench when both processes receive trusted startup roots for the same persisted capsule
  directory.
- Absolute `capsule_path` remains a portability debt in assembly state. A future durable-format
  decision may store a portable reference directly; this milestone does not migrate or rewrite
  existing assembly databases.

## Implementation Clarification — 2026-10-04

The read-only catalog opens an existing assembly database with SQLite `mode=ro`; a configured path
that is missing or unopenable must never be created by inspection. Presentation and the additive
source-status API distinguish no configured source, an unavailable configured source, a valid
source with zero captures, and a valid source with captures. Existing `GET /api/runs` list behavior
remains compatible, and no source response exposes a configured filesystem path.

## Alternatives Rejected

### Use Replay History as the Run Catalog

Rejected. Replay attempts are operational actions against evidence and may be absent, repeated, or
technically failed. They cannot define the existence or state of the original captured run.

### Copy Capsules into SQLite

Rejected. This would create a second evidence store and invite divergence from sealed filesystem
evidence.

### Let the Browser Submit a Capsule Path

Rejected. Local path selection would expose arbitrary filesystem reads to HTTP input.

### Compute Trust or Diff Semantics in JavaScript

Rejected. Presentation code must not become a second replay, integrity, diff, or regression engine.

### Add Framework Graph Fields to the Core Model

Rejected under ADR-0008. Future framework hierarchy must be translated into additive generic read
model data without changing evidence, replay, storage, diff, or regression semantics.
