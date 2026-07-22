# Start Here

This page is the five-minute orientation. Read [PROJECT_MEMORY.md](../PROJECT_MEMORY.md) first when doing architectural or implementation work.

## What Is TraceForge?

TraceForge is an experimental local developer tool for capturing a failed Python agent run as immutable evidence, replaying it offline with recorded model and tool outcomes, comparing the result, and exporting a developer-approved regression test. It is not a hosted observability platform or a production deployment.

## What Actually Works?

- Replay Capsule v0 sealing, validation, integrity, and fail-closed exact replay.
- Best-effort capture/redaction and one controlled LangGraph integration.
- Separate regression specifications, offline pytest export, and a local FastAPI/SQLite dashboard.
- Three controlled cases: weather grounding, RAG citation grounding, and tool-argument safety.
- An optional local distributed path through a Go HTTP gateway, Kafka, a Python assembly worker, sealed capsule storage, Prometheus metrics, and optional OpenTelemetry collection.

Fork replay, live replay, production capture integration, hosted operation, authentication, Kubernetes, and Terraform do not exist. Check the exact evidence and limitations in [verification-ledger.md](verification-ledger.md).

## Run the Smallest Example

From the repository root, after installing the development dependencies described in [README.md](../README.md):

```sh
traceforge validate examples/weather/replay-capsule.json
traceforge replay examples/weather/replay-capsule.json \
  --runner traceforge.examples.weather_agent:run \
  --spec examples/weather/regression-spec.json
```

The complete offline capture-to-export demonstration is:

```sh
python -m traceforge.examples.end_to_end
```

The other controlled examples are under [examples/rag-citation/](../examples/rag-citation/) and [examples/tool-argument-safety/](../examples/tool-argument-safety/).

## Run the Distributed Stack

This is local development infrastructure, not a production procedure:

```sh
docker compose -f compose.kafka.yml up -d --build
docker compose -f compose.kafka.yml ps
traceforge kafka-smoke \
  --bootstrap-servers 127.0.0.1:29092 \
  --database .traceforge-data/smoke.sqlite3 \
  --capsule-directory .traceforge-data/capsules
docker compose -f compose.kafka.yml down
```

For the Collector and cross-language trace verifier, use the exact commands in [operations/observability.md](operations/observability.md). For startup, shutdown, and failure triage, use [operations/README.md](operations/README.md).

## Where Is Each Subsystem?

| Subsystem | Location |
| --- | --- |
| Capsule schemas and fixtures | [schemas/](../schemas/) |
| Python capture, sealing, validation, replay, and regression | [src/traceforge/](../src/traceforge/) |
| Kafka publisher, assembly state, and worker | [src/traceforge/](../src/traceforge/) |
| Dashboard/API | [src/traceforge/web.py](../src/traceforge/web.py), templates, and static assets |
| Controlled examples | [examples/](../examples/) and [src/traceforge/examples/](../src/traceforge/examples/) |
| Go gateway | [services/ingest-gateway/](../services/ingest-gateway/) |
| OpenTelemetry Collector | [services/otel-collector.yaml](../services/otel-collector.yaml) |
| Docker/Compose | [Dockerfile](../Dockerfile), [Dockerfile.kafka](../Dockerfile.kafka), and [compose.kafka.yml](../compose.kafka.yml) |
| Tests | [tests/](../tests/) and Go `_test.go` files under the gateway |
| Documentation and ADRs | [docs/](.) |

See [codebase-map.md](codebase-map.md) for inputs, outputs, invariants, extension points, and tests for each component.

## What Should I Read Next?

1. [project-state.md](project-state.md) for live status, blockers, and the exact next approved task.
2. [architecture.md](architecture.md) for replay and distributed boundaries.
3. The relevant ADRs listed in [docs/README.md](README.md).
4. [codebase-map.md](codebase-map.md) and the tests for the component you will change.
5. [security.md](security.md), [testing-strategy.md](testing-strategy.md), and [verification-ledger.md](verification-ledger.md) before making claims.

## What Must Never Change Casually?

- The immutable-evidence boundary, capsule canonicalization, fingerprint, or integrity scope.
- Exact replay's frozen-output and fail-closed guarantees.
- Separation of original evidence from regression expectations and telemetry correlation.
- Capture-event ordering, `capture_id` keying, `event_id` idempotency, or at-least-once semantics.
- Local/offline defaults, trust boundaries, secret rules, or developer approval for generated assertions.
- Service ownership or an accepted ADR without a superseding ADR.
- The postponed status of Kubernetes, Terraform, hosted services, authentication, and production claims without explicit approval and measured evidence.
