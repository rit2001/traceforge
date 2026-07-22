# Observability Runbook

OpenTelemetry and Prometheus are optional local diagnostics. They must not become evidence dependencies or carry capsule payloads.

## Start and Verify the Collector Profile

```sh
docker compose --profile observability -f compose.kafka.yml up -d --build
curl -fsS http://127.0.0.1:13133/
OTEL_SDK_DISABLED=false \
  OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317 \
  OTEL_EXPORTER_OTLP_INSECURE=true \
  .venv/bin/python scripts/gateway_smoke.py
curl -fsS http://127.0.0.1:18080/metrics
curl -fsS http://127.0.0.1:19464/metrics
docker compose --profile observability -f compose.kafka.yml down
```

The smoke verifier expects one cross-service capture trace, a separate replay trace, a Span Link to capture correlation, bounded service/span names, and no known prohibited attribute values.

## Collector Unavailable

```sh
docker compose --profile observability -f compose.kafka.yml ps otel-collector
docker compose --profile observability -f compose.kafka.yml logs otel-collector
curl -i http://127.0.0.1:13133/
```

Confirm the profile is active and ports 4317/4318 are reachable from the configured services. Collector loss can drop diagnostic telemetry, but it must not modify or block capture events, sealing, capsule validation, or replay. Treat a service that cannot start because optional telemetry is unavailable as a bug in the local integration boundary.

## Missing Spans

1. Confirm `OTEL_SDK_DISABLED=false` in each instrumented process and verify its OTLP endpoint.
2. Confirm the client injects W3C context, Go injects Kafka headers, and the worker receives them.
3. Allow the SDK and Collector batch processors a short bounded flush interval before concluding spans are absent.
4. Check Collector health/logs and the ignored local trace file under `.traceforge-data/otel/` without publishing its contents.
5. Run `scripts/gateway_smoke.py`; it checks required names, the Kafka parent relationship, and the replay link.

A malformed or absent incoming context may legitimately create a new capture context. Missing SQLite correlation may legitimately produce replay without a link; it must not fail replay.

## Replay Span Link Missing

Check that the capture completed through `capsule.seal`, the worker stored capture `trace_id`/`span_id` in SQLite, and replay was invoked with that correlation. Never add trace IDs to the capsule or recompute capsule integrity to create a link. If correlation is unavailable, retain an unlinked replay trace and report the limitation.

## Metrics

Use gateway `/metrics`, worker port `19464`, API `/metrics` when the optional metrics dependency is present, and Collector-exported metrics on port `8889`. Metric labels must remain bounded and must not contain capture IDs, URLs, user input, payloads, error text, or exception text. See [docs/observability.md](../observability.md) for the owned metric list.

## Security Boundary

The local Collector endpoint is unencrypted and unauthenticated and exports to local debug/file sinks. Do not expose its ports beyond loopback, forward it to a hosted backend, or inspect/share raw trace output without explicit approval and a sensitive-data review. The bounded scan in the smoke verifier cannot prove universal secret absence.
