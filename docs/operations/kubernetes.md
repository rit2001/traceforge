# Local Kubernetes on kind

This runbook deploys the existing distributed TraceForge containers to a dedicated local kind
cluster. It is a development procedure, not a cloud or production runbook.

Docker packages and runs the individual Go and Python application containers. Kubernetes schedules,
restarts, connects, configures, probes, and constrains those containers. kind supplies one local
Kubernetes cluster inside Docker. Passing this gate does not prove cloud production readiness, high
availability, scale, durable Kafka, authentication, TLS, or a production security posture.

## Prerequisites and Safety Boundary

Use an ARM64 host with a running Docker daemon plus `kind`, `kubectl`, `make`, and the existing
project virtual environment. The automation installs nothing and contacts no model, tool, or
external application API.

Every script is fixed to cluster `traceforge`, context `kind-traceforge`, and namespace
`traceforge`. The destroy script checks for the exact cluster name and cannot delete another kind
cluster. Do not change those boundaries casually.

## Full Local Gate

Run each step separately so a failure leaves evidence available for diagnosis:

```sh
make kind-validate
make kind-create
make kind-images
make kind-apply
make kind-wait
make kind-smoke
make kind-destroy
```

`make kind-verify` runs every step except teardown. Always run `make kind-destroy` after collecting
the bounded result.

The smoke sends only the controlled weather fixture. It verifies gateway acceptance, Kafka
transport, worker sealing, capsule validation, exact offline replay and regression evaluation,
duplicate idempotency, malformed-input rejection before enqueue, cross-service spans and replay
link, API pod recreation, worker replacement with unchanged PVC capsule content, and UID/GID 10001
for application containers. It prints a sanitized outcome summary without capsule contents, user
messages, dependency responses, credentials, or raw trace identifiers.

## Local Access

There is no LoadBalancer or Ingress. Keep access explicit and local:

```sh
kubectl --context kind-traceforge --namespace traceforge \
  port-forward service/traceforge-api 18000:8000
kubectl --context kind-traceforge --namespace traceforge \
  port-forward service/ingest-gateway 18080:8080
```

Then use `http://127.0.0.1:18000/healthz` or the local dashboard. A gateway `202` still means only
bounded queue acceptance; it does not prove Kafka delivery or capsule completion.

## Architecture and Persistence

The cluster path is unchanged from Compose:

```text
port-forward -> Go gateway Service -> Kafka headless Service -> Python worker
                                                       |             |
                                                       |             +-> RWO PVC: SQLite + capsules
                                                       +-> local Collector <- OTLP spans
TraceForge API Service ----------------------------------------------> RWO PVC: history
```

Kafka and the Collector are explicitly labelled local-development infrastructure. Kafka data is
ephemeral. The one `standard` kind PVC persists worker state, capsules, API history, and a bounded
Collector trace file across pod replacement. It is deleted with the kind cluster.

The worker has one replica and `Recreate` strategy. SQLite is still single writer. Do not scale the
worker, open its live WAL from another process, or interpret a PVC as a distributed database. The
API and Collector share the filesystem claim but write separate files, not the assembly database.

## Security and Probes

The Go gateway, worker, and API run as UID/GID 10001. They disable privilege escalation, drop all
capabilities, use RuntimeDefault seccomp, and use read-only root filesystems with explicit writable
volumes. The Collector uses the same controls. Kafka runs as its supported non-root UID/GID 1000
with privilege escalation disabled and capabilities dropped, but needs a writable image filesystem
for its development entrypoint.

Gateway and API probes use their health/readiness endpoints. Kafka probes run its topic-list command.
Collector probes use its health extension. Worker probes use its metrics HTTP server, which proves
the worker process is alive but not broker progress; `make kind-smoke` proves one controlled consume
and seal path.

## Failure Triage

Keep the cluster running while diagnosing:

```sh
kubectl --context kind-traceforge --namespace traceforge get pods
kubectl --context kind-traceforge --namespace traceforge describe pods
kubectl --context kind-traceforge --namespace traceforge logs statefulset/kafka
kubectl --context kind-traceforge --namespace traceforge logs deployment/ingest-gateway
kubectl --context kind-traceforge --namespace traceforge logs deployment/traceforge-worker
kubectl --context kind-traceforge --namespace traceforge logs deployment/otel-collector
```

- `ImagePullBackOff` on a TraceForge image means `make kind-images` did not load the explicit local
  tag into the named cluster.
- An unbound PVC usually means the kind local-path provisioner is not ready; inspect the
  `local-path-storage` namespace before reapplying.
- Gateway readiness failure should be diagnosed from Kafka first. Never bypass `/readyz`.
- Worker metrics readiness without a capsule is not consumption proof. Check Kafka, worker logs,
  duplicate/DLQ metrics, and event sequencing without printing payloads.
- Collector failure may lose diagnostics but must not block capture, sealing, validation, or replay.

After diagnosis, delete only the dedicated cluster:

```sh
make kind-destroy
```
