# Git Workflow

This workflow keeps experimental evidence and implementation changes reviewable. The currently documented branch is `feat/terraform-foundation-v0.4`.

## Branches

- `main` is stable and releasable for the scope the repository actually supports. It must not carry half-finished feature work.
- Do feature work on short-lived `feat/` branches, fixes on `fix/` branches, and documentation/governance work on `docs/` branches.
- Do not perform direct feature work on `main`. Urgent fixes still use a focused `fix/` branch and review.
- Keep one approved milestone per branch. Rebase or merge according to repository maintainer preference without rewriting shared evidence history.

## Commits

- Scope each commit to one coherent behaviour, test, documentation, or governance change.
- Keep generated caches, virtual environments, local SQLite files, capsule output, Collector output, coverage output, and build artifacts out of commits.
- Commit generated source artifacts only when they are intentional reviewed deliverables, reproducible, and required by the repository; document the generator and review the diff.
- Never commit credentials, `.env` files or contents, tokens, authorization material, unsanitized traces, unreviewed production data, or local absolute paths.

## Pull Requests and CI

1. Read [PROJECT_MEMORY.md](../PROJECT_MEMORY.md), [project-state.md](project-state.md), relevant ADRs, and the affected component docs.
2. Inspect the current branch and working tree; preserve unrelated changes.
3. Implement the smallest approved diff with focused tests and synchronized authoritative docs.
4. Run offline formatting, lint, Python tests, relevant Go tests, link/path checks, and `git diff --check` as applicable.
5. Open a pull request that states scope, acceptance criteria, evidence, security impact, documentation changes, skipped checks, assumptions, and rollback.
6. Require CI to pass before merge. A maintainer must review capsule/contract, security-boundary, and generated-assertion changes explicitly.
7. Merge only when the branch is complete and `main` remains releasable.

CI passing proves only the tested repository scope. It does not authorize or substantiate production claims.

## Releases and Rollback

- Create release tags from reviewed commits on `main`, using the repository's chosen semantic version once a release is approved.
- Tags must identify the source commit; never move or silently replace a published release tag.
- Roll back by deploying or reverting to an existing known-good commit, or by a reviewed revert commit. Do not erase shared history to hide a faulty release.
- Capsule schema or evidence-semantic rollback must preserve version dispatch and existing evidence readability; use an ADR and migration plan for incompatible changes.

## Current Branch

`feat/terraform-foundation-v0.4` contains the approved local Terraform foundation around the existing kind/Kustomize deployment. It is not evidence that the branch has merged to `main`, shipped as a release, deployed to a cloud, verified AWS/EKS, or completed production hardening.
