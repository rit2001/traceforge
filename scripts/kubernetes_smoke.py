"""Real kind smoke, recovery, persistence, and security verification."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from traceforge.examples.weather_agent import run
from traceforge.kafka_runtime import capsule_events
from traceforge.replay import CallableFrameworkAdapter, replay_exact
from traceforge.store import JsonFileCapsuleStore
from traceforge.validation import validate_capsule

ROOT = Path(__file__).resolve().parents[1]
GATEWAY_URL = "http://127.0.0.1:18080"
TRACE_PATH = "/data/traces.json"


@dataclass(frozen=True)
class Kubernetes:
    context: str
    namespace: str

    def command(
        self,
        *args: str,
        input_data: bytes | None = None,
        check: bool = True,
        timeout: float = 60,
    ) -> subprocess.CompletedProcess[bytes]:
        completed = subprocess.run(
            ["kubectl", "--context", self.context, "--namespace", self.namespace, *args],
            input=input_data,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        if check and completed.returncode != 0:
            error = completed.stderr.decode(errors="replace").strip()
            raise RuntimeError(f"kubectl {' '.join(args)} failed: {error}")
        return completed

    def pod(self, application_name: str, timeout: float = 90) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.command(
                "get",
                "pods",
                "--selector",
                f"app.kubernetes.io/name={application_name}",
                "--output",
                "json",
            )
            items = json.loads(result.stdout).get("items", [])
            for item in items:
                conditions = item.get("status", {}).get("conditions", [])
                ready = any(
                    condition.get("type") == "Ready" and condition.get("status") == "True"
                    for condition in conditions
                )
                if item.get("status", {}).get("phase") == "Running" and ready:
                    return str(item["metadata"]["name"])
            time.sleep(0.5)
        raise RuntimeError(f"timed out waiting for ready pod {application_name}")

    def exec(
        self,
        pod: str,
        container: str,
        *args: str,
        check: bool = True,
        timeout: float = 30,
    ) -> subprocess.CompletedProcess[bytes]:
        return self.command(
            "exec", pod, "--container", container, "--", *args, check=check, timeout=timeout
        )

    def worker_read(self, path: str, *, missing_ok: bool = False) -> bytes | None:
        pod = self.pod("traceforge-worker")
        program = (
            "from pathlib import Path; import sys; p=Path(sys.argv[1]); "
            "sys.exit(3) if not p.is_file() else sys.stdout.buffer.write(p.read_bytes())"
        )
        result = self.exec(pod, "worker", "python", "-c", program, path, check=False)
        if result.returncode == 3 and missing_ok:
            return None
        if result.returncode != 0:
            error = result.stderr.decode(errors="replace").strip()
            raise RuntimeError(f"could not read worker path {path}: {error}")
        return result.stdout

    def worker_http(self, url: str) -> str:
        pod = self.pod("traceforge-worker")
        program = (
            "import sys,urllib.request; "
            "sys.stdout.write(urllib.request.urlopen(sys.argv[1], timeout=3).read().decode())"
        )
        return self.exec(pod, "worker", "python", "-c", program, url).stdout.decode()

    def rollout(self, workload: str, timeout: str = "180s") -> None:
        self.command("rollout", "status", workload, f"--timeout={timeout}", timeout=210)


class PortForward:
    def __init__(self, kube: Kubernetes, resource: str, mapping: str, local_port: int) -> None:
        self.kube = kube
        self.resource = resource
        self.mapping = mapping
        self.local_port = local_port
        self.process: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> PortForward:
        self.process = subprocess.Popen(
            [
                "kubectl",
                "--context",
                self.kube.context,
                "--namespace",
                self.kube.namespace,
                "port-forward",
                self.resource,
                self.mapping,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"port-forward exited for {self.resource}")
            try:
                with socket.create_connection(("127.0.0.1", self.local_port), timeout=0.25):
                    return self
            except OSError:
                time.sleep(0.2)
        self.close()
        raise RuntimeError(f"timed out starting port-forward for {self.resource}")

    def close(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()


def post(body: bytes, trace_headers: dict[str, str] | None = None) -> int:
    request = urllib.request.Request(
        f"{GATEWAY_URL}/v1/capture-events",
        body,
        {"content-type": "application/json", **(trace_headers or {})},
        method="POST",
    )
    try:
        return urllib.request.urlopen(request, timeout=5).status
    except urllib.error.HTTPError as exc:
        return exc.code


def http_text(url: str) -> str:
    return urllib.request.urlopen(url, timeout=5).read().decode()


def metric_value(text: str, name: str) -> float:
    values = []
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        metric_name = line.split("{", 1)[0].split(" ", 1)[0]
        if metric_name == name:
            values.append(float(line.rsplit(" ", 1)[1]))
    if not values:
        raise RuntimeError(f"metric not found: {name}")
    return sum(values)


def trace_spans(raw: bytes) -> list[tuple[str, dict[str, object]]]:
    spans: list[tuple[str, dict[str, object]]] = []
    for line in raw.decode().splitlines():
        document = json.loads(line)
        for resource_spans in document.get("resourceSpans", []):
            attributes = resource_spans.get("resource", {}).get("attributes", [])
            service = next(
                (
                    attribute["value"]["stringValue"]
                    for attribute in attributes
                    if attribute.get("key") == "service.name"
                ),
                "unknown",
            )
            for scope in resource_spans.get("scopeSpans", []):
                spans.extend((service, item) for item in scope.get("spans", []))
    return spans


def wait_for_sealed_context(kube: Kubernetes, capture_trace_id: str) -> dict[str, str]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        raw = kube.worker_read(TRACE_PATH, missing_ok=True)
        if raw:
            capture = [
                item for _, item in trace_spans(raw) if item.get("traceId") == capture_trace_id
            ]
            consume_ids = {
                item.get("spanId") for item in capture if item.get("name") == "capture.consume"
            }
            seal = next((item for item in capture if item.get("name") == "capsule.seal"), None)
            if seal is not None and seal.get("parentSpanId") in consume_ids:
                return {"trace_id": capture_trace_id, "span_id": str(seal["parentSpanId"])}
        time.sleep(0.5)
    raise RuntimeError("Collector did not expose the sealed capture context")


def verify_telemetry(
    kube: Kubernetes, correlation: dict[str, str], replay_trace_id: str
) -> dict[str, object]:
    expected = {
        "traceforge-ingest-gateway": {"capture.receive", "capture.validate", "capture.publish"},
        "traceforge-capsule-worker": {"capture.consume", "capsule.assemble", "capsule.seal"},
    }
    deadline = time.monotonic() + 30
    spans: list[tuple[str, dict[str, object]]] = []
    while time.monotonic() < deadline:
        raw = kube.worker_read(TRACE_PATH, missing_ok=True)
        spans = trace_spans(raw) if raw else []
        capture = [
            (service, item)
            for service, item in spans
            if item.get("traceId") == correlation["trace_id"]
        ]
        replay = [
            item
            for _, item in spans
            if item.get("traceId") == replay_trace_id and item.get("name") == "replay.execute"
        ]
        observed: dict[str, set[str]] = {}
        for service, item in capture:
            observed.setdefault(service, set()).add(str(item.get("name")))
        if all(
            names <= observed.get(service, set()) for service, names in expected.items()
        ) and any(
            link.get("traceId") == correlation["trace_id"]
            and link.get("spanId") == correlation["span_id"]
            for item in replay
            for link in item.get("links", [])
        ):
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("Collector did not expose the required capture and replay spans")

    capture = [
        (service, item) for service, item in spans if item.get("traceId") == correlation["trace_id"]
    ]
    publish_ids = {
        item.get("spanId")
        for service, item in capture
        if service == "traceforge-ingest-gateway" and item.get("name") == "capture.publish"
    }
    consume_parents = {
        item.get("parentSpanId")
        for service, item in capture
        if service == "traceforge-capsule-worker" and item.get("name") == "capture.consume"
    }
    if not publish_ids.intersection(consume_parents):
        raise RuntimeError("worker span is not descended from the Kafka publish span")
    replay_span = next(
        (
            item
            for _, item in spans
            if item.get("traceId") == replay_trace_id and item.get("name") == "replay.execute"
        ),
        None,
    )
    if replay_span is None:
        raise RuntimeError("replay span is absent")
    attribute_text = json.dumps(
        [item.get("attributes", []) for _, item in capture] + [replay_span.get("attributes", [])]
    ).lower()
    prohibited = {"authorization", "api_key", "bearer ", "kolkata", "umbrella", "light rain"}
    leaked = sorted(value for value in prohibited if value in attribute_text)
    if leaked:
        raise RuntimeError(f"prohibited values found in span attributes: {leaked}")
    return {
        "required_spans": "passed",
        "kafka_parent_link": "passed",
        "replay_span_link": "passed",
        "bounded_attribute_scan": "passed",
    }


def wait_for_capsule(kube: Kubernetes, path: str) -> bytes:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        content = kube.worker_read(path, missing_ok=True)
        if content:
            return content
        time.sleep(0.5)
    raise RuntimeError("timed out waiting for the worker to seal a capsule")


def wait_for_metric(kube: Kubernetes, name: str, minimum: float) -> float:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        value = metric_value(kube.worker_http("http://127.0.0.1:9464/metrics"), name)
        if value >= minimum:
            return value
        time.sleep(0.5)
    raise RuntimeError(f"metric {name} did not reach {minimum}")


def remote_uid(kube: Kubernetes, application: str, container: str) -> dict[str, int]:
    pod = kube.pod(application)
    uid = int(kube.exec(pod, container, "id", "-u").stdout.strip())
    gid = int(kube.exec(pod, container, "id", "-g").stdout.strip())
    if uid == 0 or gid == 0:
        raise RuntimeError(f"{application} is running as root")
    return {"uid": uid, "gid": gid}


def recover_pod(kube: Kubernetes, application: str, workload: str) -> tuple[str, str]:
    previous = kube.pod(application)
    kube.command("delete", "pod", previous, "--wait=true", timeout=90)
    kube.rollout(workload)
    current = kube.pod(application)
    if current == previous:
        raise RuntimeError(f"{workload} did not create a replacement pod")
    return previous, current


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", default="kind-traceforge")
    parser.add_argument("--namespace", default="traceforge")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.context != "kind-traceforge" or args.namespace != "traceforge":
        raise RuntimeError("smoke verification is restricted to kind-traceforge/traceforge")
    kube = Kubernetes(args.context, args.namespace)
    workloads = ["kafka", "otel-collector", "ingest-gateway", "traceforge-worker", "traceforge-api"]
    for workload in workloads:
        kube.pod(workload)

    os.environ["OTEL_SDK_DISABLED"] = "false"
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://127.0.0.1:4317"
    os.environ["OTEL_EXPORTER_OTLP_INSECURE"] = "true"
    from opentelemetry import propagate

    from traceforge.observability import (
        configure,
        current_correlation,
        last_replay_correlation,
        shutdown,
        span,
    )

    provider: Any = None
    with (
        PortForward(kube, "service/ingest-gateway", "18080:8080", 18080),
        PortForward(kube, "service/otel-collector", "4317:4317", 4317),
    ):
        provider = configure("traceforge-kubernetes-smoke-client")
        source = JsonFileCapsuleStore().load(ROOT / "examples/weather/replay-capsule.json")
        spec = JsonFileCapsuleStore().load(ROOT / "examples/weather/regression-spec.json")
        capture_id = f"kubernetes-smoke-{uuid4().hex[:12]}"
        events = capsule_events(source, capture_id)
        target = f"/data/capsules/{capture_id}.json"
        try:
            with span("capture.smoke"):
                headers: dict[str, str] = {}
                propagate.inject(headers)
                capture_context = current_correlation()
                statuses = [post(json.dumps(event).encode(), headers) for event in events]
            if any(status != 202 for status in statuses):
                raise RuntimeError(f"capture events were not accepted: {statuses}")
            if not capture_context:
                raise RuntimeError("smoke client did not create capture trace context")

            capsule_bytes = wait_for_capsule(kube, target)
            capsule = json.loads(capsule_bytes)
            validate_capsule(capsule)
            correlation = wait_for_sealed_context(kube, capture_context["trace_id"])
            replay = replay_exact(
                capsule, CallableFrameworkAdapter(run), spec, correlation=correlation
            )
            replay_context = last_replay_correlation()
            if replay.regression is None or not replay.regression.passed:
                raise RuntimeError("offline replay regression failed")
            if not replay_context or replay_context["trace_id"] == capture_context["trace_id"]:
                raise RuntimeError("replay did not produce its required separate trace")
        finally:
            shutdown(provider)
            provider = None

        duplicate_before = metric_value(
            kube.worker_http("http://127.0.0.1:9464/metrics"),
            "traceforge_worker_duplicate_events_total",
        )
        duplicate_statuses = [post(json.dumps(event).encode(), headers) for event in events]
        if any(status != 202 for status in duplicate_statuses):
            raise RuntimeError("duplicate events were not accepted for idempotency verification")
        wait_for_metric(
            kube,
            "traceforge_worker_duplicate_events_total",
            duplicate_before + len(events),
        )
        worker = kube.pod("traceforge-worker")
        count_program = (
            "from pathlib import Path; import sys; "
            "print(len(list(Path(sys.argv[1]).glob(sys.argv[2]))))"
        )
        capsule_count = int(
            kube.exec(
                worker,
                "worker",
                "python",
                "-c",
                count_program,
                "/data/capsules",
                f"{capture_id}*.json",
            ).stdout
        )
        if capsule_count != 1:
            raise RuntimeError(f"duplicate delivery produced {capsule_count} capsules")

        accepted_before = metric_value(
            http_text(f"{GATEWAY_URL}/metrics"), "traceforge_gateway_accepted_events_total"
        )
        malformed = post(b"{")
        accepted_after = metric_value(
            http_text(f"{GATEWAY_URL}/metrics"), "traceforge_gateway_accepted_events_total"
        )
        if malformed != 400 or accepted_after != accepted_before:
            raise RuntimeError("malformed input was not rejected before gateway enqueue")

        telemetry = verify_telemetry(kube, correlation, replay_context["trace_id"])

    old_api, new_api = recover_pod(kube, "traceforge-api", "deployment/traceforge-api")
    api = kube.pod("traceforge-api")
    health_program = (
        "import urllib.request; "
        "print(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status)"
    )
    if kube.exec(api, "api", "python", "-c", health_program).stdout.strip() != b"200":
        raise RuntimeError("replacement API pod did not serve its health endpoint")

    persisted_before = capsule_bytes
    old_worker, new_worker = recover_pod(kube, "traceforge-worker", "deployment/traceforge-worker")
    persisted_after = wait_for_capsule(kube, target)
    if persisted_after != persisted_before:
        raise RuntimeError("persisted capsule changed across worker replacement")
    validate_capsule(json.loads(persisted_after))

    non_root = {
        "ingest-gateway": remote_uid(kube, "ingest-gateway", "ingest-gateway"),
        "traceforge-worker": remote_uid(kube, "traceforge-worker", "worker"),
        "traceforge-api": remote_uid(kube, "traceforge-api", "api"),
    }
    if any(identity != {"uid": 10001, "gid": 10001} for identity in non_root.values()):
        raise RuntimeError(f"application UID/GID did not match 10001: {non_root}")

    evidence = {
        "workloads_ready": workloads,
        "capture": "sealed-and-validated",
        "offline_replay": "regression-passed",
        "duplicate_delivery": "idempotent-one-capsule",
        "malformed_input": "rejected-400-before-enqueue",
        "telemetry": telemetry,
        "stateless_pod_recovery": {
            "deployment": "traceforge-api",
            "replacement_observed": old_api != new_api,
            "health": "passed",
        },
        "worker_persistence": {
            "replacement_observed": old_worker != new_worker,
            "capsule_unchanged_and_valid": True,
        },
        "application_non_root": non_root,
    }
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
