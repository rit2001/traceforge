# Repository Rules for Codex

TraceForge is an experimental replay-first project with an optional local distributed-ingestion path. Codex must keep changes small, explicit, and tied to one approved milestone.

## Operating Rules

- Work on one approved milestone only.
- Before architectural or implementation work, read `PROJECT_MEMORY.md` first.
- Read `docs/project-state.md`, relevant accepted ADRs, and the component documents linked from `docs/README.md`.
- Inspect `git status` and the current branch before editing.
- Explain the implementation plan and acceptance criteria before making application-code changes.
- Never inspect, print, copy, transform, or expose secrets.
- Never access, create, edit, rename, or infer contents from `.env` files.
- Preserve user changes. Do not revert edits you did not make unless explicitly asked.
- Treat tests as offline by default.
- Do not make paid or external API calls without explicit approval.
- Do not install dependencies without explicit approval.
- Do not add infrastructure before measured need.
- Never fabricate metrics, users, adoption, benchmarks, reliability, or production claims.
- Do not commit or push unless explicitly requested.
- Run relevant tests before finishing when tests exist and can run offline.
- Report unresolved risks, skipped tests, and assumptions.
- Prefer small, reviewable diffs.
- After material work, update `docs/project-state.md` when a milestone is completed, a blocker/assumption changes, or the approved next task changes.
- Update `docs/codebase-map.md` whenever responsibilities, important inputs/outputs, invariants, or extension seams move.
- Update `docs/verification-ledger.md` only with evidence actually executed; include the command or method, result, environment, date, revision, and limitations.
- Add or supersede an ADR for significant cross-cutting or hard-to-reverse decisions. Never silently rewrite an accepted ADR's history.
- Update the relevant runbook under `docs/operations/` when material work introduces or verifies a new failure mode or recovery path.
- Never silently rewrite historical evidence. Retain older evidence and record a clearly dated superseding entry.
- Keep `PROJECT_MEMORY.md` synchronized when a durable boundary, invariant, accepted decision set, milestone, next approved milestone, or reading contract changes.
- Keep documentation and code consistent.
- Report detected documentation drift.

## Product Boundaries

- First support only Python, LangGraph, and tool-calling agents.
- Initial execution is local-only.
- Exact replay freezes model and tool outputs.
- Fork replay freezes tool outputs but runs the model or prompt again.
- AI-generated assertions always require developer approval before becoming regression tests.
- The approved local Go/Kafka/Collector path is optional development infrastructure and must not change replay semantics.
- Do not add Terraform, Kubernetes, ClickHouse, SaaS authentication, payment systems, or production infrastructure without a separately approved evidence-based milestone and ADR where required.

For durable repository memory start with `PROJECT_MEMORY.md`. For detailed product, architecture, roadmap, testing, security, operations, and terminology ownership, use `docs/README.md` instead of duplicating long-form content here.
