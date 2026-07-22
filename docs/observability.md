# Local observability

TraceForge can emit local OpenTelemetry traces across the capture path without putting telemetry metadata into Replay Capsules. Telemetry is optional and disabled by default. The Compose observability profile sends OTLP only to the pinned local Collector; it does not configure an external backend.

## Trace flow

An instrumented client sends W3C `traceparent` and optional `tracestate` headers to the Go gateway. The gateway extracts that context, creates `capture.receive`, `capture.validate`, and `capture.publish`, and injects the resulting W3C context into Kafka record headers. The Python worker attaches that context only while processing the message and creates `capture.consume`; a completed stream also creates `capsule.assemble` and `capsule.seal`.

Replay is deliberately later and separate. `replay.execute` starts a new trace and may contain a Span Link to capture correlation stored in SQLite. Trace IDs and span IDs are operational metadata: they are not added to or used to rewrite immutable capsule evidence. Missing correlation does not block replay.

Service names are `traceforge-ingest-gateway`, `traceforge-capsule-worker`, and `traceforge-api`. The instrumented local verifier uses `traceforge-smoke-client`.

## Configuration and local verification

Go and Python service startup own provider/exporter configuration. Reusable packages do not configure exporters during import. Set `OTEL_SDK_DISABLED=false` and standard OTLP variables such as `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_INSECURE` to enable local exporting. Otherwise Python and Go tracing boundaries are no-ops.

Start and verify the local stack:

```sh
docker compose --profile observability -f compose.kafka.yml up -d --build
OTEL_SDK_DISABLED=false \
  OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317 \
  OTEL_EXPORTER_OTLP_INSECURE=true \
  .venv/bin/python scripts/gateway_smoke.py
curl http://127.0.0.1:13133/
curl http://127.0.0.1:18080/metrics
curl http://127.0.0.1:19464/metrics
docker compose --profile observability -f compose.kafka.yml down
```

For the local kind topology, use the bounded verifier and Collector access described in the [Kubernetes runbook](operations/kubernetes.md). It preserves the same span, metric, and evidence-separation rules.

The smoke command prints distinct capture and replay trace IDs, verifies the replay link, checks required span names and service names, and writes a sanitized summary to the ignored `.traceforge-data/otel/verification-summary.json`. Raw local Collector output is also ignored under `.traceforge-data/otel/`.

If spans are initially absent, allow for the SDK and Collector batch processors. Check the Collector health endpoint and logs, confirm the observability profile is active, and verify that OTLP receivers are reachable on ports 4317 or 4318.

On Docker Desktop, do not open the worker's bind-mounted SQLite database concurrently from a host process. Inspect it inside the worker service or after Compose shutdown; cross-boundary WAL inspection is not a supported coordination mechanism.

## Metrics

The Go gateway exposes:

- `traceforge_gateway_requests_total`
- `traceforge_gateway_accepted_events_total`
- `traceforge_gateway_rejected_events_total`
- `traceforge_gateway_queue_full_total`
- `traceforge_gateway_delivery_failures_total`
- `traceforge_gateway_http_duration_seconds`

The Python worker/API expose:

- `traceforge_worker_consumed_events_total`
- `traceforge_worker_duplicate_events_total`
- `traceforge_worker_dlq_events_total`
- `traceforge_worker_sealed_capsules_total`
- `traceforge_worker_processing_duration_seconds`
- `traceforge_replay_total`, with only `success` or `failure` as its label value

Identifiers, URLs, user input, error messages, and exception text are not metric labels.

## Security and limitations

Spans do not contain capture payloads, dependency responses, authorization values, API keys, or raw user messages. Gateway validation errors are recorded using generic descriptions. Automatic HTTP instrumentation still records bounded transport metadata such as method, route, body size, peer address, and user agent.

The local Collector uses an unencrypted, unauthenticated development endpoint and a debug/file exporter. It is not a production topology. The local attribute scan checks known prohibited strings but is not a mathematical guarantee of secret absence. Logs remain ordinary structured `slog` or Python logs; TraceForge does not claim stable OpenTelemetry log support.
