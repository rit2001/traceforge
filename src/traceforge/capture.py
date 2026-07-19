"""Small capture SDK with sanitization before draft persistence."""

from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic_ns
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_NAMES = {
    "api-key",
    "api_key",
    "apikey",
    "authorization",
    "client-secret",
    "client_secret",
    "cookie",
    "cookies",
    "secret",
    "set-cookie",
    "token",
    "access-token",
    "access_token",
}
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|token|client[_-]?secret|secret)=([^&\s]+)"
)
BEARER_TOKEN = re.compile(r"(?i)(authorization\s*:\s*bearer|bearer)\s+[^\s,;]+")


@dataclass(frozen=True)
class ScanResult:
    value: Any
    actions: tuple[dict[str, str], ...]


class BestEffortRedactionScanner:
    """Versioned key/header/query scanner; it cannot prove secret absence."""

    policy_version = "best-effort-v1"

    def scan(self, value: Any, path: str = "$") -> ScanResult:
        actions: list[dict[str, str]] = []
        sanitized = self._sanitize(deepcopy(value), path, actions)
        return ScanResult(sanitized, tuple(actions))

    def _sanitize(self, value: Any, path: str, actions: list[dict[str, str]]) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                normalized = key.lower().replace("_", "-")
                child_path = f"{path}.{key}"
                if normalized in SENSITIVE_NAMES:
                    actions.append({"path": child_path, "action": "removed"})
                    continue
                if key == "url" and isinstance(item, str):
                    result[key] = self._sanitize_url(item, child_path, actions)
                elif key == "headers" and isinstance(item, dict):
                    result[key] = self._sanitize_headers(item, child_path, actions)
                else:
                    result[key] = self._sanitize(item, child_path, actions)
            return result
        if isinstance(value, list):
            return [
                self._sanitize(item, f"{path}[{index}]", actions)
                for index, item in enumerate(value)
            ]
        if isinstance(value, str):
            sanitized = SECRET_ASSIGNMENT.sub(r"\1=[removed]", value)
            sanitized = BEARER_TOKEN.sub(r"\1 [removed]", sanitized)
            if sanitized != value:
                actions.append({"path": path, "action": "masked"})
            return sanitized
        return value

    def _sanitize_headers(
        self, headers: dict[str, Any], path: str, actions: list[dict[str, str]]
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in headers.items():
            if key.lower() == "content-type":
                result["content-type"] = value
            else:
                actions.append({"path": f"{path}.{key}", "action": "removed"})
        return result

    def _sanitize_url(self, url: str, path: str, actions: list[dict[str, str]]) -> str:
        parts = urlsplit(url)
        query: list[tuple[str, str]] = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key.lower().replace("_", "-") in SENSITIVE_NAMES:
                actions.append({"path": f"{path}.query.{key}", "action": "removed"})
            else:
                query.append((key, value))
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )


Executor = Callable[[Any], dict[str, Any]]


class CaptureSession:
    """Collect external fixtures and internal evidence for one local run."""

    def __init__(
        self,
        *,
        capsule_id: str,
        run_id: str,
        capture_kind: str,
        producer: dict[str, str],
        subject: dict[str, str],
        operation: str,
        invocation_input: Any,
        scanner: BestEffortRedactionScanner | None = None,
        recorded_at: str | None = None,
    ) -> None:
        self.scanner = scanner or BestEffortRedactionScanner()
        self._actions: list[dict[str, str]] = []
        self._dependencies: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []
        self._base = {
            "schema_version": "0.1.0",
            "capsule_id": capsule_id,
            "capture": {
                "run_id": run_id,
                "kind": capture_kind,
                "recorded_at": recorded_at
                or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "producer": producer,
            "subject": subject,
            "invocation": {
                "operation": operation,
                "input": self._scan(invocation_input, "$.invocation.input"),
            },
        }

    def _scan(self, value: Any, path: str) -> Any:
        result = self.scanner.scan(value, path)
        self._actions.extend(result.actions)
        return result.value

    def _record_dependency(
        self, kind: str, operation: str, request: Any, executor: Executor
    ) -> dict[str, Any]:
        sequence = len(self._dependencies) + 1
        started = monotonic_ns()
        try:
            response = executor(deepcopy(request))
            outcome = {
                "status": "returned",
                "response": self._scan(
                    response, f"$.dependencies[{sequence - 1}].outcome.response"
                ),
            }
        except Exception as exc:  # capture must retain application dependency failures
            outcome = {
                "status": "errored",
                "error": self._scan(
                    {"type": type(exc).__name__, "message": str(exc), "data": None},
                    f"$.dependencies[{sequence - 1}].outcome.error",
                ),
            }
        duration_ms = max(0, (monotonic_ns() - started) // 1_000_000)
        dependency = {
            "dependency_id": f"dependency-{sequence}",
            "sequence": sequence,
            "kind": kind,
            "operation": operation,
            "request": self._scan(request, f"$.dependencies[{sequence - 1}].request"),
            "outcome": outcome,
            "duration_ms": duration_ms,
        }
        self._dependencies.append(dependency)
        return deepcopy(outcome)

    def record_model(
        self, operation: str, request: dict[str, Any], executor: Executor
    ) -> dict[str, Any]:
        return self._record_dependency("model", operation, request, executor)

    def record_http(
        self, operation: str, request: dict[str, Any], executor: Executor
    ) -> dict[str, Any]:
        return self._record_dependency("http", operation, request, executor)

    def record_event(self, kind: str, name: str, data: Any) -> None:
        sequence = len(self._events) + 1
        self._events.append(
            {
                "event_id": f"event-{sequence}",
                "sequence": sequence,
                "kind": kind,
                "name": name,
                "data": self._scan(data, f"$.original_observation.events[{sequence - 1}].data"),
            }
        )

    def finish(self, execution_status: str, output: Any, error: Any = None) -> dict[str, Any]:
        """Return an unsealed sanitized draft; fingerprints are intentionally absent."""
        draft = deepcopy(self._base)
        draft["dependencies"] = deepcopy(self._dependencies)
        draft["original_observation"] = {
            "execution_status": execution_status,
            "events": deepcopy(self._events),
            "output": self._scan(output, "$.original_observation.output"),
            "error": self._scan(error, "$.original_observation.error"),
        }
        draft["redaction"] = {
            "policy_version": self.scanner.policy_version,
            "actions": deepcopy(self._actions),
            "scan_result": "passed",
        }
        return draft
