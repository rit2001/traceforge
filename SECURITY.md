# Security Policy

## Project Status

TraceForge is an Experimental Beta for local evaluation and contributor development. It does not claim a formal enterprise security program, production hardening, tenant isolation, or safe execution of untrusted code.

Only the current `0.4.x` line receives security fixes during the public-beta phase. Older experimental versions may be used to understand history but should not be assumed to receive patches.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability.

Use [GitHub's private vulnerability reporting](https://github.com/rit2001/traceforge/security/advisories/new) when available. If that channel is unavailable, contact the repository owner privately through the contact method on the [`@rit2001`](https://github.com/rit2001) profile before sharing details.

Include, using synthetic data only:

- the affected TraceForge version or commit;
- the affected component and configuration;
- minimal reproduction steps;
- likely impact and prerequisites; and
- any safe mitigation you have identified.

The maintainer will acknowledge the report when practical, investigate it, and coordinate disclosure based on severity and available maintainer capacity. No fixed response-time or remediation SLA is promised during the Experimental Beta.

## Sensitive Material

Never submit or attach:

- real API keys, OAuth tokens, GitHub tokens, cloud credentials, database passwords, or private keys;
- production credentials or authorization headers;
- `.env` files or their contents;
- real sensitive Replay Capsules, private customer data, or private traces;
- unsanitized logs, local SQLite databases, Terraform state, or generated replay artifacts.

Use synthetic fixtures and replace sensitive identifiers before sharing a reproduction.

## Current Security Boundaries

- Redaction is best effort and cannot guarantee that all sensitive data has been found.
- Replay runners and startup-registered dashboard runners are trusted local Python code with the process's authority.
- The socket-level replay guard reduces accidental network access but is not an operating-system sandbox.
- The FastAPI workbench is unauthenticated and should remain bound to localhost.
- Docker Compose, kind/Kustomize, and Terraform assets are local-development infrastructure, not production-secure deployment guidance.
- OpenTelemetry and Prometheus endpoints may reveal operational metadata and should not be exposed publicly without separate controls.

Review every capsule, fixture, log, and generated test before persistence, publication, or commit. See [docs/security.md](docs/security.md) for the detailed threat model and trust boundaries.
