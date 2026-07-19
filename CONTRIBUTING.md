# Contributing

TraceForge is an experimental replay-first MVP. Keep contributions small, local-first, and tied to an approved milestone.

1. Create a focused branch.
2. Do not add credentials, `.env` data, unsanitized traces, or copied application code.
3. Install development extras with `python -m pip install -e ".[dev]"`.
4. Run `ruff format --check src tests`, `ruff check src tests`, and `pytest`.
5. Update the canonical documentation owner when behaviour changes.

New framework integrations belong behind `FrameworkAdapter`; storage belongs behind `CapsuleStore`. Captured evidence must remain immutable. Please open an issue before adding infrastructure or changing the Replay Capsule contract.
