# Go ingestion gateway

The Go gateway keeps HTTP capture ingestion isolated from the Python replay engine. It validates bounded JSON requests, sanitizes obvious secret-bearing material, enqueues records asynchronously to Kafka, and returns `202 Accepted` only when the bounded local queue accepts the record. Queue saturation returns `429`; unavailable readiness returns `503`; malformed, oversized, or unsafe requests return `400`, `413`, or `415`.

Kafka delivery failures happen after acceptance and are counted separately. The gateway never flushes Kafka per request. Its shutdown path is bounded. Structured logs contain error types and status, never event payloads.

Run locally with `docker compose -f compose.kafka.yml up --build`. The gateway listens on `127.0.0.1:18080`. `GET /healthz` reports process health; `GET /readyz` reports whether the Kafka-backed queue is accepting work.

The local kind deployment runs this same image and configuration behind a ClusterIP Service. Access it only through the loopback port-forward in the [Kubernetes runbook](../operations/kubernetes.md); `202`, readiness, and backpressure semantics are unchanged.

The image contains immutable capture-event 0.2 and successor 0.3 schemas. Startup loads both
through explicit version dispatch (`CAPTURE_EVENT_SCHEMA` and `CAPTURE_EVENT_SCHEMA_V03`), so an
unsupported version or a 0.3-only `execution_span_recorded` type under a 0.2 envelope returns
`400` before enqueue. The 0.3 span payload is structurally validated at ingress. Gateway
validation still does not make a transport event evidence; assembly and capsule sealing remain
the evidence boundary.

With the Compose `observability` profile, application startup configures the optional OTLP exporter. W3C HTTP trace context is continued through `capture.receive`, `capture.validate`, and `capture.publish`, then injected into Kafka headers. See [Local observability](../observability.md) for verification commands and limitations.
