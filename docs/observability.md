# Local observability

Cross-service OpenTelemetry is not implemented yet. The Collector configuration remains behind the inactive Compose `observability` profile and is not part of the verified gateway workflow.

The intended boundary keeps capture and replay as separate traces and correlates them outside immutable capsule evidence. Telemetry must never rewrite a capsule.
