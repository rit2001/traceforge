# Contributing to TraceForge

TraceForge is an Experimental Beta. Contributions are welcome when they are focused, evidence-based, and aligned with an approved roadmap milestone. The project is replay-first: preserve immutable captured evidence, keep developer expectations separate, and do not weaken fail-closed exact replay.

## Where to Begin

Good starting points are documentation corrections, focused tests, controlled-example improvements, and issues explicitly labeled `good first issue` or `help wanted`. For cross-cutting architecture, open a design issue before writing implementation code.

Before working on a change, read:

1. [PROJECT_MEMORY.md](PROJECT_MEMORY.md);
2. [the current project state](docs/project-state.md);
3. [the documentation index](docs/README.md); and
4. the relevant accepted [architecture decisions](docs/decisions/).

## Development Prerequisites

- Python 3.10 or newer;
- Go version declared by [`services/ingest-gateway/go.mod`](services/ingest-gateway/go.mod);
- Docker with Compose for the optional distributed path;
- `kubectl` and `kustomize` for manifest validation;
- Terraform for the optional local foundation; and
- GNU Make only where a documented helper uses it.

Do not install dependencies or make external API calls without understanding the cost and trust boundary. Repository tests are offline by default.

## Local Setup

```bash
git clone https://github.com/rit2001/traceforge.git
cd traceforge
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,dashboard,langgraph,kafka,observability]"
```

Never copy credentials or `.env` contents into this repository. Use only synthetic or reviewed, sanitized Replay Capsules.

## Python Checks

```bash
python -m pytest -q
ruff check src tests scripts
ruff format --check src tests scripts
python -m build --wheel --no-isolation
```

Run a focused test while iterating, then the complete repository suite before opening a pull request. If local third-party pytest plugins interfere, document the isolated invocation and its limitation rather than hiding the environment difference.

## Go Checks

Run these from `services/ingest-gateway`:

```bash
go test ./...
go vet ./...
go test -race ./...
test -z "$(gofmt -l .)"
```

## Infrastructure Checks

Use the commands and safety boundaries in the relevant runbook under [`docs/operations/`](docs/operations/). At minimum, changes should exercise the applicable existing checks for:

- `docker compose config`;
- Kustomize rendering and ownership checks;
- `terraform fmt -check -recursive`; and
- the repository's Terraform/static verification tests.

Do not treat a successful local kind or Terraform check as production, cloud, security, availability, or scale evidence.

## Docker Compose

The replay core does not require Kafka. For the optional local distributed path, follow [the Kafka runbook](docs/operations/kafka.md) and keep services bound to local development interfaces.

Validate configuration before starting it:

```bash
docker compose -f deploy/docker-compose.yml config
```

## Branches and Commits

Create a focused branch from current `main`. Supported branch prefixes are:

```text
feat/*
fix/*
docs/*
test/*
refactor/*
chore/*
perf/*
```

TraceForge does not use a permanent `develop` branch. Use [Conventional Commits](https://www.conventionalcommits.org/) with a clear scope, for example:

```text
fix(kafka): preserve source offset on DLQ failure
docs(replay): clarify exact replay boundaries
test(capture): cover duplicate event handling
```

Keep commits reviewable. Do not mix broad formatting, architecture changes, and behavior changes in one commit.

## Pull Request Expectations

A pull request should:

- explain what changed and why;
- identify the approved milestone or issue;
- include exact test commands and results;
- disclose skipped checks, environment failures, assumptions, and limitations;
- preserve backward compatibility or explain the contract impact;
- update the canonical documentation owner for changed behavior;
- add an ADR for a significant cross-cutting or hard-to-reverse decision; and
- avoid unrelated refactors.

Only record verification evidence that was actually executed. Never silently rewrite older evidence; add a dated superseding entry when needed.

## Architecture and Design Discussions

Open a design issue before changing Replay Capsule semantics, capture-event compatibility, replay modes, storage ownership, delivery guarantees, framework boundaries, or infrastructure ownership. Include constraints, alternatives, failure modes, replay implications, observability implications, compatibility risks, and unresolved questions.

Current product boundaries support Python, LangGraph, and tool-calling agents first. Exact replay freezes recorded model and dependency outputs. Fork replay is planned, not implemented. The optional Go/Kafka/Collector path must not change replay semantics.

## Security and Data Handling

Do not submit:

- real API keys, tokens, credentials, or private keys;
- `.env` files or their contents;
- real sensitive replay traces or private customer data;
- local SQLite databases, Terraform state/plans, generated capsules, or debug artifacts; or
- logs that have not been reviewed and sanitized.

Redaction is best effort, not proof that an artifact is safe. Report suspected vulnerabilities privately according to [SECURITY.md](SECURITY.md); do not open a public issue with sensitive details.

By contributing, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md) and license your contribution under the [Apache License 2.0](LICENSE).
