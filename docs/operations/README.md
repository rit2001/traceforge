# Local Operations

These are concise troubleshooting notes for the optional local Compose and kind topologies. They are development runbooks, not production procedures, SLOs, or evidence of operational readiness.

For the native-Kustomize local Kubernetes deployment, use the dedicated [kind runbook](kubernetes.md). For the Terraform-backed foundation and ordered ownership lifecycle, use the [Terraform runbook](terraform.md). For the localhost replay workbench and trusted custom runner registration, use the [dashboard runbook](dashboard.md). The Compose commands below remain valid for the original single-host topology.

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
| Terraform plan/state/drift/destroy or foundation ownership | [Local Terraform](terraform.md) |
| Tool capture rejects sensitive arguments or replay rejects an exception type | [Tool-boundary failures](#tool-boundary-failures) |
| SQLite bind-mount warning | [SQLite bind-mount warning](#sqlite-bind-mount-warning) |

## Tool-Boundary Failures

If tool capture reports that redaction would change request identity, do not disable the check or
persist the raw value. Remove non-semantic credentials before the boundary, or provide a reviewed
application-owned deterministic sanitizer that maps identity-bearing data to stable safe JSON.
Use the same sanitizer during capture and replay, and verify distinct meaningful inputs retain
distinct fingerprints.

If exact replay rejects an unsupported recorded tool exception type, the runner has not executed.
Do not import a class named by capsule evidence or replace it with a generic catchable error. Add a
new allow-listed mapping only through a reviewed contract change with a control-flow test, or treat
that recorded failure as not exactly replayable by the current version.

If `CaptureSession.finish()` raises `UnreplayableCaptureError`, a live tool already returned a
result that the standard scanner could not persist unchanged. The application received that result
normally, but no legal exact-replay draft exists. Do not recover by storing the raw or transformed
result, and do not treat the condition as a tool failure. Discard the pending capture. A future
result-projection contract requires a separate reviewed decision.

## SQLite Bind-Mount Warning

On Docker Desktop, do not open the worker's bind-mounted SQLite database concurrently from a host process while the worker owns its WAL. Cross-boundary host inspection is not a supported coordination mechanism and may show misleading state or locking behaviour. Inspect through a service-owned reader, or stop Compose cleanly before opening the database from the host.

## General Triage Rules

- Preserve capsule, SQLite, Kafka, and Collector artifacts until the failure scope is understood.
- Check health/readiness, service logs, and bounded metrics before restarting.
- Do not paste event payloads, capsule contents, headers, or raw traces into issues until they pass security review.
- A `202` response proves queue acceptance only; it does not prove Kafka delivery, worker processing, capsule sealing, or replay success.
- Collector failure must not block capture, sealing, or replay. Kafka/worker failure can delay capsule creation.
