# Kafka and Ingestion Runbook

Use this only for the local [Compose topology](../../compose.kafka.yml). Commands inspect local service state; they do not define production operations.

## Kafka Unavailable

Symptoms include gateway `503`, delivery-failure metrics, worker consume errors, or an unhealthy `kafka` service.

```sh
docker compose -f compose.kafka.yml ps
docker compose -f compose.kafka.yml logs kafka
curl -i http://127.0.0.1:18080/readyz
```

Confirm the broker health check passes and the gateway is configured for the Compose listener `kafka:19092`. After Kafka recovers, recheck readiness. Events that never entered the gateway queue must be resubmitted by the client. A prior `202` still does not by itself prove broker delivery; inspect delivery-failure metrics and downstream capsule state.

## Gateway Unready

```sh
curl -i http://127.0.0.1:18080/healthz
curl -i http://127.0.0.1:18080/readyz
docker compose -f compose.kafka.yml logs ingest-gateway
```

If health passes and readiness fails, check Kafka first. If both fail, inspect service/container startup and configuration. Do not bypass readiness or reinterpret `503` as acceptance.

## Queue Full

A full bounded publisher queue returns `429` and increments `traceforge_gateway_queue_full_total`.

```sh
curl -fsS http://127.0.0.1:18080/metrics
docker compose -f compose.kafka.yml logs ingest-gateway
docker compose -f compose.kafka.yml ps kafka
```

Stop or slow the local producer, restore broker progress, and retry rejected events with the same stable event IDs. Do not enlarge the queue until the failure is reproduced and memory/backpressure trade-offs are measured.

## Worker Not Consuming

```sh
docker compose -f compose.kafka.yml ps traceforge-worker kafka
docker compose -f compose.kafka.yml logs traceforge-worker
curl -fsS http://127.0.0.1:19464/metrics
```

Check that Kafka is healthy, the worker uses topic `traceforge.capture.v1` and group `traceforge-assembler-v1`, and its `/data` mount is writable by the service user. No worker health check currently exists, so container-running status alone does not prove consumption. Preserve SQLite state before restarting; manual commits mean uncommitted records may be redelivered and must be deduplicated.

## DLQ Growth

The worker sends malformed or semantically unsafe records to `traceforge.capture.dlq.v1` and commits the source record only after confirmed DLQ delivery.

```sh
docker compose -f compose.kafka.yml logs traceforge-worker
curl -fsS http://127.0.0.1:19464/metrics
```

Track `traceforge_worker_dlq_events_total` and error types. Do not print raw DLQ payloads until they have been reviewed for secrets. Identify whether failures are malformed JSON, schema violations, sequence gaps, conflicting duplicates, or a version mismatch. Fix the producer or compatibility path; do not edit sealed capsules or silently discard the DLQ.

## Capsule Not Appearing

Work from the boundary where evidence last exists:

1. Confirm every gateway POST returned `202`; a `400/413/415/429/503` event was not accepted.
2. Check gateway accepted, queue-full, and delivery-failure metrics.
3. Check worker consumed, duplicate, DLQ, and sealed-capsule metrics.
4. Look for sequence-gap or conflict errors in worker logs.
5. Confirm the stream begins with `capture_started`, has contiguous positive sequences, and ends with `capture_completed`.
6. Inspect the configured host-visible capsule directory only after respecting the SQLite WAL warning in [README.md](README.md#sqlite-bind-mount-warning).

Do not manually create a capsule from partial events. Repair the transport input and replay it through assembly so validation and sealing remain authoritative.

## Bounded Smoke Check

With the stack healthy:

```sh
traceforge kafka-smoke \
  --bootstrap-servers 127.0.0.1:29092 \
  --database .traceforge-data/smoke.sqlite3 \
  --capsule-directory .traceforge-data/capsules
```

This verifies one local controlled route to a sealed capsule and exact replay. It is not a load, outage-duration, durability, or production test.
