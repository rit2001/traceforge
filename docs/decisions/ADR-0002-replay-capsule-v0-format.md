# ADR-0002: Replay Capsule v0 Format

Status: Accepted

Date: 2026-07-18

## Context

The replay feasibility spike needs a portable boundary between capture and future validation, sealing, replay, diff, and test-export work. That boundary must preserve sanitized evidence, describe deterministic external fixtures, and remain inspectable with ordinary local tools. It must not imply production readiness or pull postponed storage and packaging concerns into the spike.

The format also needs deterministic request identities and a deterministic whole-document integrity calculation. Structural validation and semantic validation have different responsibilities and must not be conflated.

## Decision

Replay Capsule v0 is one UTF-8 JSON document with schema version `0.1.0`. Its normative contract is [Replay Capsule v0](../contracts/replay-capsule-v0.md), and its structure uses JSON Schema Draft 2020-12.

Request fingerprints use SHA-256 over the RFC 8785 JSON Canonicalization Scheme (JCS) canonicalization of the sanitized request. Capsule integrity uses SHA-256 over the RFC 8785 canonicalization of the capsule with only `integrity.digest` omitted.

The capsule keeps immutable original evidence separate from mutable regression expectations. Expectations are not embedded in v0 and remain developer-approved artifacts managed outside the capsule.

External model and HTTP dependency records use a normalized common shape: identifier, sequence, kind, operation, sanitized request, request fingerprint, returned-or-errored outcome, and diagnostic duration. Kind-specific request and response structures preserve the information required for deterministic fixture matching while HTTP headers are restricted to explicitly safe normalized fields.

Replay matches a fixture using both sequence and sanitized request identity. Missing or mismatched fixtures fail closed; there is no live fallback.

## Alternatives Postponed

### Directory-Based Capsules

Directories could separate metadata and payloads, but introduce atomicity, naming, traversal, partial-copy, and integrity-scope questions that the v0 evidence model does not need.

### ZIP Archives

ZIP archives could package multiple files, but add archive parsing, path-safety, compression, deterministic-archive, and tooling concerns before attachments are required.

### Database Records

A database could support indexing and queries, but would couple the feasibility boundary to storage, schema migration, and service-lifecycle decisions before local replay value is established.

### Binary Blobs

Binary blobs could carry attachments or opaque framework state, but complicate sanitization, review, portability, canonicalization, and diffing. Binary attachments are postponed until a measured replay case requires them.

## Consequences

- Capsules are human-inspectable and compatible with standard JSON tooling.
- A single canonicalization method defines stable fingerprints and integrity inputs across conforming implementations.
- Structural JSON Schema validation remains separate from semantic checks for digests, fingerprints, uniqueness, redaction effectiveness, request matching, and zero-network replay.
- Evidence can remain stable while separately stored expectations evolve.
- Normalized dependency records constrain v0 adapters and may require explicit conversion from framework-native traces.
- The one-document choice limits v0 to JSON-compatible sanitized data and excludes binary attachments.
- Failing closed favors safety and determinism over convenience when capture is incomplete.
- This decision defines a feasibility-spike contract and makes no production-readiness claim.

## Migration and Versioning

Readers must dispatch on `schema_version` and reject unsupported versions rather than guessing. Backward-compatible clarification may retain `0.1.0`; any structural or semantic change that alters valid documents, canonicalized data, fingerprint inputs, integrity scope, or replay meaning requires a new schema version and an explicit migration path.

Future formats may introduce a directory, archive, database representation, binary attachment manifest, or additional dependency kinds. Such changes must preserve the ability to identify the source version, validate before migration, avoid silently rewriting evidence, and recompute fingerprints or integrity only under clearly versioned rules.
