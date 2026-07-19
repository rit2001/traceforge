"""Bounded real HTTP gateway to Kafka to replay smoke workflow."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from traceforge.examples.weather_agent import run
from traceforge.kafka_runtime import capsule_events
from traceforge.replay import CallableFrameworkAdapter, replay_exact
from traceforge.store import JsonFileCapsuleStore
from traceforge.validation import validate_capsule

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:18080/v1/capture-events"


def post(body: bytes, content_type: str = "application/json") -> int:
    request = urllib.request.Request(URL, body, {"content-type": content_type}, method="POST")
    try:
        return urllib.request.urlopen(request, timeout=5).status
    except urllib.error.HTTPError as exc:
        return exc.code


def main() -> int:
    store = JsonFileCapsuleStore()
    source = store.load(ROOT / "examples/weather/replay-capsule.json")
    spec = store.load(ROOT / "examples/weather/regression-spec.json")
    events = capsule_events(source, "gateway-smoke-capture")
    statuses = [post(json.dumps(event).encode()) for event in events]
    if any(status != 202 for status in statuses):
        raise RuntimeError(f"unexpected POST statuses: {statuses}")
    target = ROOT / ".traceforge-data/capsules/gateway-smoke-capture.json"
    deadline = time.monotonic() + 30
    while not target.is_file() and time.monotonic() < deadline:
        time.sleep(0.25)
    sealed = store.load(target)
    validate_capsule(sealed)
    result = replay_exact(sealed, CallableFrameworkAdapter(run), spec)
    if result.regression is None or not result.regression.passed:
        raise RuntimeError("offline replay regression failed")
    duplicate = [post(json.dumps(event).encode()) for event in events]
    malformed = post(b"{")
    files = list(target.parent.glob("gateway-smoke-capture*.json"))
    output = {
        "accepted": statuses,
        "duplicate": duplicate,
        "malformed": malformed,
        "capsules": len(files),
        "replay_passed": True,
    }
    print(json.dumps(output, sort_keys=True))
    return 0 if malformed == 400 and len(files) == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
