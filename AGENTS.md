# Repository Rules for Codex

TraceForge is in a replay-feasibility phase. Codex must keep changes small, explicit, and tied to the approved milestone.

## Operating Rules

- Work on one approved milestone only.
- Before implementation, read `docs/README.md` and `docs/project-state.md`.
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
- Update `docs/project-state.md` when a milestone is completed or the approved next task changes.
- Add an ADR for significant cross-cutting or hard-to-reverse decisions.
- Keep documentation and code consistent.
- Report detected documentation drift.

## Product Boundaries

- First support only Python, LangGraph, and tool-calling agents.
- Initial execution is local-only.
- Exact replay freezes model and tool outputs.
- Fork replay freezes tool outputs but runs the model or prompt again.
- AI-generated assertions always require developer approval before becoming regression tests.
- Do not add Go, Kafka, Terraform, Kubernetes, ClickHouse, SaaS authentication, or payment systems before the replay feasibility spike passes.

For detailed product, architecture, roadmap, testing, security, and terminology ownership, use `docs/README.md` as the documentation index instead of duplicating long-form content here.
