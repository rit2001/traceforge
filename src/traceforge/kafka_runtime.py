"""Optional Kafka runtime wiring around the durable assembly worker."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from traceforge.assembly import SQLiteAssemblyState
from traceforge.kafka_worker import KafkaAssemblyWorker
from traceforge.metrics import start_worker_metrics
from traceforge.observability import configure
from traceforge.store import JsonFileCapsuleStore
from traceforge.validation import validate_capsule


def create_worker(
    bootstrap: str,
    topic: str,
    dlq_topic: str,
    group: str,
    database: Path,
    directory: Path,
) -> KafkaAssemblyWorker:
    try:
        from confluent_kafka import Consumer, Producer
    except ImportError as exc:
        raise RuntimeError(
            "Kafka support requires the 'kafka' extra: pip install traceforge-replay[kafka]"
        ) from exc
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": group,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([topic])
    telemetry_provider = configure("traceforge-capsule-worker")
    start_worker_metrics()
    return KafkaAssemblyWorker(
        consumer,
        Producer({"bootstrap.servers": bootstrap}),
        SQLiteAssemblyState(database, directory),
        dlq_topic,
        telemetry_provider,
    )


def capsule_events(capsule: dict[str, Any], capture_id: str) -> list[dict[str, Any]]:
    """Convert one sealed capsule into a sanitized transport event stream."""
    excluded = {"dependencies", "original_observation", "redaction", "integrity"}
    base = {key: value for key, value in capsule.items() if key not in excluded}
    events: list[dict[str, Any]] = []
    sequence = 1
    events.append(_event(capture_id, sequence, "capture_started", base))
    sequence += 1
    for dependency in capsule["dependencies"]:
        events.append(_event(capture_id, sequence, "dependency_recorded", dependency))
        sequence += 1
    for observation in capsule["original_observation"]["events"]:
        events.append(_event(capture_id, sequence, "observation_recorded", observation))
        sequence += 1
    events.append(
        _event(
            capture_id,
            sequence,
            "capture_completed",
            {
                "original_observation": capsule["original_observation"],
                "redaction": capsule["redaction"],
            },
        )
    )
    return events


def _event(capture_id: str, sequence: int, event_type: str, payload: Any) -> dict[str, Any]:
    return {
        "schema_version": "0.2.0",
        "event_id": f"{capture_id}-event-{sequence}",
        "capture_id": capture_id,
        "sequence": sequence,
        "event_type": event_type,
        "occurred_at": "2026-07-19T12:00:00Z",
        "producer": {"name": "traceforge-smoke", "version": "0.2.0"},
        "payload": payload,
    }


def kafka_smoke(bootstrap: str, database: Path, directory: Path) -> str:
    try:
        from confluent_kafka import Producer
    except ImportError as exc:
        raise RuntimeError(
            "Kafka support requires the 'kafka' extra: pip install traceforge-replay[kafka]"
        ) from exc
    from traceforge.examples.weather_agent import run as weather_runner
    from traceforge.replay import CallableFrameworkAdapter, replay_exact

    capsule = JsonFileCapsuleStore().load(Path("examples/weather/replay-capsule.json"))
    spec = JsonFileCapsuleStore().load(Path("examples/weather/regression-spec.json"))
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    producer = Producer({"bootstrap.servers": bootstrap})
    for event in capsule_events(capsule, "kafka-smoke-capture"):
        producer.produce(
            "traceforge.capture.v1",
            key=event["capture_id"].encode(),
            value=json.dumps(event, sort_keys=True).encode(),
        )
    producer.flush(10)
    target = directory / "kafka-smoke-capture.json"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if target.is_file():
            sealed = JsonFileCapsuleStore().load(target)
            validate_capsule(sealed)
            result = replay_exact(sealed, CallableFrameworkAdapter(weather_runner), spec)
            if result.regression is None or not result.regression.passed:
                raise RuntimeError("Kafka smoke replay regression failed")
            return json.dumps(
                {"capsule": str(target), "replay": result.to_dict()},
                ensure_ascii=False,
                sort_keys=True,
            )
        time.sleep(0.25)
    raise RuntimeError(f"timed out waiting for sealed capsule {target}")
