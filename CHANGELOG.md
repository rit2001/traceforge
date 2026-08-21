# Changelog

All notable changes to TraceForge are documented here. This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses [Semantic Versioning](https://semver.org/) for software releases. Replay Capsule and Capture Event schema versions are independent from the software version.

## [Unreleased]

### Changed

- Synchronized durable project state after the `v0.4.1` GitHub publication and protection gate.

## [0.4.1] - 2026-08-21

### Added

- Public documentation for the replay-first product, current limitations, contributor workflow, security policy, roadmap, and GitHub community processes.
- Installed-package data for the controlled examples, schemas, workbench templates, and styles.
- Trusted startup registration for allow-listed local workbench runners.

### Changed

- Aligned package, CLI, container, and release metadata on `0.4.1` and Apache License 2.0.
- Expanded the local replay workbench while preserving its unauthenticated localhost-only boundary.
- Aligned the Python Kafka publisher default with the `traceforge.capture.v1` runtime topic.
- Reconciled architecture and project-state documentation so fork replay is explicitly planned rather than implemented.

### Verified

- Exact offline replay and regression behavior across the controlled examples.
- Python, Go, packaging, Docker Compose, Kustomize, and Terraform/static checks recorded in the [verification ledger](docs/verification-ledger.md).

### Known Limitations

- Capture is controlled and framework support is bounded; arbitrary agents and generic tools are not supported.
- Fork replay and fresh-model replay are not implemented.
- The distributed path is local development infrastructure and does not establish production, cloud, scale, availability, or performance claims.

[Unreleased]: https://github.com/rit2001/traceforge/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/rit2001/traceforge/releases/tag/v0.4.1
