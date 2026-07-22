# Contributing

TraceForge is an experimental replay-first MVP. Keep contributions small, local-first, and tied to an approved milestone.

1. Read [PROJECT_MEMORY.md](PROJECT_MEMORY.md), [project state](docs/project-state.md), relevant ADRs, and the affected component documents.
2. Inspect the current branch and working tree, preserve unrelated changes, and create a focused branch using [the Git workflow](docs/git-workflow.md).
3. Do not add credentials, `.env` data, unsanitized traces, copied application code, or local absolute paths.
4. Install development extras with `python -m pip install -e ".[dev]"` only when dependency installation is approved.
5. Run `ruff format --check src tests`, `ruff check src tests`, `pytest`, and relevant Go/integration checks offline.
6. Update the canonical documentation owner when behaviour changes. Add only executed evidence to the [verification ledger](docs/verification-ledger.md).
7. Open a focused pull request and require CI before merge; do not do direct feature work on `main`.

New framework integrations belong behind `FrameworkAdapter`; storage belongs behind `CapsuleStore`. Captured evidence must remain immutable. Add or supersede an ADR before changing hard-to-reverse architecture or the Replay Capsule contract. Kubernetes, Terraform, hosted operation, and production infrastructure require a separately approved milestone.
