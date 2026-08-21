## What changed

<!-- Describe the focused change. -->

## Why

<!-- Link the approved milestone, problem, or design discussion. -->

## How tested

<!-- List exact commands, results, environment details, and skipped checks. -->

- [ ] Relevant offline tests passed.
- [ ] Formatting and lint checks passed.
- [ ] `git diff --check` passed.

## Limitations

<!-- State unresolved risks, assumptions, and what this change does not prove. -->

## Architecture / compatibility impact

<!-- Cover Replay Capsule, Capture Event, replay semantics, adapters, storage, or backward compatibility. Write "None" when applicable. -->

## Operational impact

<!-- Required for infrastructure/runtime changes: deployment, configuration, metrics, failure modes, rollback, and runbook updates. Otherwise write "None". -->

## Related issue

<!-- Example: Closes #123 -->

## Safety checklist

- [ ] No credentials, `.env` content, authorization material, private data, or unsanitized traces were added.
- [ ] Generated artifacts, local databases, Terraform state/plans, and debug output were not committed.
- [ ] Documentation reflects implemented, partial, and planned behavior accurately.
- [ ] No external or paid API runs were added to default tests or CI.
