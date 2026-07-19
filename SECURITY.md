# Security Policy

TraceForge is an experimental local MVP, not a production security product.

Report suspected vulnerabilities privately to the repository owner rather than opening a public issue containing sensitive details. Include affected version, reproduction steps using synthetic data, and likely impact. Do not include real credentials, private traces, or `.env` contents.

The best-effort scanner removes known sensitive keys, unsafe HTTP headers, and known secret query parameters, but cannot guarantee detection of every secret or sensitive value. Review every capsule before persistence, sharing, or commit. Bind the unauthenticated dashboard to localhost and treat dynamic CLI runners as trusted local code.

See [docs/security.md](docs/security.md) for the current trust boundaries and limitations.
