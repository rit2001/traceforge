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

from traceforge.canonical import canonicalize
from traceforge.exceptions import (
    SemanticValidationError,
    UnreplayableCaptureError,
    UnsafeToolArgumentsError,
    recorded_tool_exception_type,
)

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
ToolExecutor = Callable[[Any], Any]
ToolArgumentSanitizer = Callable[[Any], Any]


def sanitize_tool_arguments(
    arguments: Any,
    *,
    scanner: BestEffortRedactionScanner | None = None,
    sanitizer: ToolArgumentSanitizer | None = None,
    path: str = "$.tool.arguments",
) -> ScanResult:
    """Return safe identity-bearing arguments or reject before tool execution."""
    active_scanner = scanner or BestEffortRedactionScanner()
    if sanitizer is None:
        scanned = active_scanner.scan(arguments, path)
        if scanned.actions:
            raise UnsafeToolArgumentsError(
                "tool arguments require an explicit deterministic sanitizer before tool execution "
                "because default redaction would change request identity"
            )
        canonicalize(scanned.value)
        return scanned

    try:
        first = deepcopy(sanitizer(deepcopy(arguments)))
        first_canonical = canonicalize(first)
        second = deepcopy(sanitizer(deepcopy(arguments)))
        second_canonical = canonicalize(second)
    except Exception as exc:
        raise UnsafeToolArgumentsError("tool argument deterministic sanitizer failed") from exc
    if first_canonical != second_canonical:
        raise UnsafeToolArgumentsError(
            "tool argument deterministic sanitizer returned different identities for the same input"
        )

    scanned = active_scanner.scan(first, path)
    if scanned.actions:
        raise UnsafeToolArgumentsError(
            "tool argument deterministic sanitizer left values requiring generic redaction"
        )
    actions: tuple[dict[str, str], ...] = ()
    if first != arguments:
        actions = ({"path": path, "action": "pseudonymized"},)
    return ScanResult(scanned.value, actions)


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
        schema_version: str = "0.1.0",
        scanner: BestEffortRedactionScanner | None = None,
        recorded_at: str | None = None,
    ) -> None:
        self.scanner = scanner or BestEffortRedactionScanner()
        self._uses_standard_tool_scanner = type(self.scanner) is BestEffortRedactionScanner
        self._tool_result_prevents_exact_replay = False
        self._actions: list[dict[str, str]] = []
        self._dependencies: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []
        self._base = {
            "schema_version": schema_version,
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

    def record_tool(
        self,
        operation: str,
        arguments: Any,
        executor: ToolExecutor,
        *,
        sanitizer: ToolArgumentSanitizer | None = None,
    ) -> Any:
        """Execute one live tool, recording a safe result or re-raised failure."""
        if self._base["schema_version"] != "0.2.0":
            raise SemanticValidationError(
                "generic tool dependencies require Replay Capsule schema_version '0.2.0'"
            )
        if not isinstance(operation, str) or not operation:
            raise SemanticValidationError(
                "tool operation must be a non-empty stable logical identity"
            )
        if not self._uses_standard_tool_scanner:
            raise SemanticValidationError(
                "generic tool capture requires the standard scanner contract"
            )
        sequence = len(self._dependencies) + 1
        request_path = f"$.dependencies[{sequence - 1}].request.arguments"
        scanned_arguments = sanitize_tool_arguments(
            arguments,
            scanner=self.scanner,
            sanitizer=sanitizer,
            path=request_path,
        )
        self._actions.extend(scanned_arguments.actions)
        started = monotonic_ns()
        try:
            result = executor(deepcopy(arguments))
        except Exception as exc:
            outcome = {
                "status": "errored",
                "error": self._scan(
                    {
                        "type": recorded_tool_exception_type(exc),
                        "message": str(exc),
                        "data": None,
                    },
                    f"$.dependencies[{sequence - 1}].outcome.error",
                ),
            }
            self._dependencies.append(
                {
                    "dependency_id": f"dependency-{sequence}",
                    "sequence": sequence,
                    "kind": "tool",
                    "operation": operation,
                    "request": {"arguments": scanned_arguments.value},
                    "outcome": outcome,
                    "duration_ms": max(0, (monotonic_ns() - started) // 1_000_000),
                }
            )
            raise

        result_path = f"$.dependencies[{sequence - 1}].outcome.response.result"
        try:
            scanned_result = self.scanner.scan(result, result_path)
            result_is_unchanged = not scanned_result.actions and canonicalize(
                result
            ) == canonicalize(scanned_result.value)
        except Exception:
            result_is_unchanged = False
        if not result_is_unchanged:
            self._tool_result_prevents_exact_replay = True
            return result

        outcome = {
            "status": "returned",
            "response": {"result": scanned_result.value},
        }
        self._dependencies.append(
            {
                "dependency_id": f"dependency-{sequence}",
                "sequence": sequence,
                "kind": "tool",
                "operation": operation,
                "request": {"arguments": scanned_arguments.value},
                "outcome": outcome,
                "duration_ms": max(0, (monotonic_ns() - started) // 1_000_000),
            }
        )
        return result

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
        if self._tool_result_prevents_exact_replay:
            raise UnreplayableCaptureError(
                "capture cannot produce exact-replay evidence because a successful tool result "
                "could not be persisted unchanged"
            )
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
