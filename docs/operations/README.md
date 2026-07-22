# Local Operations

These are concise troubleshooting notes for the optional local Compose and kind topologies. They are development runbooks, not production procedures, SLOs, or evidence of operational readiness.

For the native-Kustomize local Kubernetes deployment, use the dedicated [kind runbook](kubernetes.md). The Compose commands below remain valid for the original single-host topology.

## Clean Startup

```sh
docker compose -f compose.kafka.yml up -d --build
docker compose -f compose.kafka.yml ps
curl -fsS http://127.0.0.1:18080/healthz
curl -fsS http://127.0.0.1:18080/readyz
curl -fsS http://127.0.0.1:18000/healthz
```

Kafka must become healthy before the dependent services start. Gateway health means the process is alive; readiness means its Kafka-backed queue currently accepts work.

For traces, start with the `observability` profile as described in [observability.md](observability.md).

## Clean Shutdown

```sh
docker compose -f compose.kafka.yml down
```

Ordinary `down` preserves the Kafka named volume and host-visible data directory. Do not add a volume-deleting flag during routine troubleshooting; deleting local data is a separate, explicit, destructive action.

## Symptom Index

| Symptom | First runbook |
| --- | --- |
| Kafka unavailable, gateway unready, queue full, worker stalled, DLQ growth, capsule absent | [Kafka and ingestion](kafka.md) |
| Collector unavailable, spans missing, trace link missing, metrics questions | [Observability](observability.md) |
| kind cluster, Kustomize, image loading, pod recovery, or PVC persistence | [Local Kubernetes](kubernetes.md) |
| SQLite bind-mount warning | [SQLite bind-mount warning](#sqlite-bind-mount-warning) |

## SQLite Bind-Mount Warning

On Docker Desktop, do not open the worker's bind-mounted SQLite database concurrently from a host process while the worker owns its WAL. Cross-boundary host inspection is not a supported coordination mechanism and may show misleading state or locking behaviour. Inspect through a service-owned reader, or stop Compose cleanly before opening the database from the host.

## General Triage Rules

- Preserve capsule, SQLite, Kafka, and Collector artifacts until the failure scope is understood.
- Check health/readiness, service logs, and bounded metrics before restarting.
- Do not paste event payloads, capsule contents, headers, or raw traces into issues until they pass security review.
- A `202` response proves queue acceptance only; it does not prove Kafka delivery, worker processing, capsule sealing, or replay success.
- Collector failure must not block capture, sealing, or replay. Kafka/worker failure can delay capsule creation.
