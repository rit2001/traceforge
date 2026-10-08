"""Small capture SDK with sanitization before draft persistence."""

from __future__ import annotations

import asyncio
import re
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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
PORTABLE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PORTABLE_LABEL_MAX_LENGTH = 256


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
        self._execution_spans: list[dict[str, Any]] = []
        self._execution_span_stack: list[str] = []
        self._execution_span_owner: tuple[int, int | None] | None = None
        self._execution_span_lock = threading.RLock()
        self._base = {
            "schema_version": schema_version,
            "capsule_id": capsule_id,
            "capture": {
                "run_id": run_id,
                "kind": capture_kind,
                "recorded_at": recorded_at
                or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "producer": deepcopy(producer),
            "subject": deepcopy(subject),
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
        execution_span_id = self._current_execution_span_id()
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
        if execution_span_id is not None:
            dependency["execution_span_id"] = execution_span_id
        self._dependencies.append(dependency)
        return deepcopy(outcome)

    def _current_execution_span_id(self) -> str | None:
        if self._base["schema_version"] != "0.3.0":
            return None
        with self._execution_span_lock:
            if not self._execution_span_stack:
                raise SemanticValidationError(
                    "Replay Capsule 0.3 dependencies and events require an active execution span"
                )
            self._require_execution_context_owner()
            return self._execution_span_stack[-1]

    @staticmethod
    def _execution_context_identity() -> tuple[int, int | None]:
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None
        return threading.get_ident(), None if task is None else id(task)

    def _require_execution_context_owner(self) -> None:
        if self._execution_span_owner != self._execution_context_identity():
            raise SemanticValidationError(
                "CaptureSession execution spans cannot be shared across threads or async tasks"
            )

    @contextmanager
    def execution_span(
        self,
        execution_span_id: str,
        *,
        kind: str,
        name: str,
        component: str,
    ) -> Iterator[None]:
        """Record one explicitly nested portable execution boundary for a 0.3 capture."""
        if self._base["schema_version"] != "0.3.0":
            raise SemanticValidationError(
                "portable execution spans require Replay Capsule schema_version '0.3.0'"
            )
        if (
            not isinstance(execution_span_id, str)
            or PORTABLE_IDENTIFIER.fullmatch(execution_span_id) is None
        ):
            raise SemanticValidationError(
                "execution_span_id must be a valid stable portable identifier"
            )
        labels: dict[str, str] = {}
        for field, value in (("kind", kind), ("name", name), ("component", component)):
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > PORTABLE_LABEL_MAX_LENGTH
                or any(ord(character) < 32 or ord(character) == 127 for character in value)
            ):
                raise SemanticValidationError(
                    f"execution span {field} must be a non-blank portable label of at most "
                    f"{PORTABLE_LABEL_MAX_LENGTH} characters without control characters"
                )
            scanned = self.scanner.scan(
                value, f"$.execution_spans[{len(self._execution_spans)}].{field}"
            )
            if scanned.actions or scanned.value != value:
                raise SemanticValidationError(
                    f"execution span {field} must already be a safe stable label"
                )
            labels[field] = value

        with self._execution_span_lock:
            if self._execution_span_stack:
                self._require_execution_context_owner()
            if any(
                execution_span["execution_span_id"] == execution_span_id
                for execution_span in self._execution_spans
            ):
                raise SemanticValidationError(f"duplicate execution_span_id {execution_span_id!r}")
            if not self._execution_span_stack and self._execution_spans:
                raise SemanticValidationError(
                    "Replay Capsule 0.3 permits exactly one root execution span"
                )
            if not self._execution_span_stack:
                self._execution_span_owner = self._execution_context_identity()
            execution_span = {
                "execution_span_id": execution_span_id,
                "parent_execution_span_id": (
                    self._execution_span_stack[-1] if self._execution_span_stack else None
                ),
                "sequence": len(self._execution_spans) + 1,
                **labels,
            }
            self._execution_spans.append(execution_span)
            self._execution_span_stack.append(execution_span_id)
        try:
            yield
        finally:
            with self._execution_span_lock:
                self._require_execution_context_owner()
                popped = self._execution_span_stack.pop()
                if popped != execution_span_id:
                    raise SemanticValidationError("execution span nesting became inconsistent")
                if not self._execution_span_stack:
                    self._execution_span_owner = None

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
        if self._base["schema_version"] not in {"0.2.0", "0.3.0"}:
            raise SemanticValidationError(
                "generic tool dependencies require Replay Capsule schema_version '0.2.0' or '0.3.0'"
            )
        execution_span_id = self._current_execution_span_id()
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
            dependency = {
                "dependency_id": f"dependency-{sequence}",
                "sequence": sequence,
                "kind": "tool",
                "operation": operation,
                "request": {"arguments": scanned_arguments.value},
                "outcome": outcome,
                "duration_ms": max(0, (monotonic_ns() - started) // 1_000_000),
            }
            if execution_span_id is not None:
                dependency["execution_span_id"] = execution_span_id
            self._dependencies.append(dependency)
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
        dependency = {
            "dependency_id": f"dependency-{sequence}",
            "sequence": sequence,
            "kind": "tool",
            "operation": operation,
            "request": {"arguments": scanned_arguments.value},
            "outcome": outcome,
            "duration_ms": max(0, (monotonic_ns() - started) // 1_000_000),
        }
        if execution_span_id is not None:
            dependency["execution_span_id"] = execution_span_id
        self._dependencies.append(dependency)
        return result

    def record_event(self, kind: str, name: str, data: Any) -> None:
        execution_span_id = self._current_execution_span_id()
        sequence = len(self._events) + 1
        event = {
            "event_id": f"event-{sequence}",
            "sequence": sequence,
            "kind": kind,
            "name": name,
            "data": self._scan(data, f"$.original_observation.events[{sequence - 1}].data"),
        }
        if execution_span_id is not None:
            event["execution_span_id"] = execution_span_id
        self._events.append(event)

    def finish(self, execution_status: str, output: Any, error: Any = None) -> dict[str, Any]:
        """Return an unsealed sanitized draft; fingerprints are intentionally absent."""
        with self._execution_span_lock:
            if self._execution_span_stack:
                self._require_execution_context_owner()
                raise SemanticValidationError(
                    "cannot finish capture while an execution span is active"
                )
            if self._base["schema_version"] == "0.3.0" and not self._execution_spans:
                raise SemanticValidationError("Replay Capsule 0.3 requires one root execution span")
        if self._tool_result_prevents_exact_replay:
            raise UnreplayableCaptureError(
                "capture cannot produce exact-replay evidence because a successful tool result "
                "could not be persisted unchanged"
            )
        draft = deepcopy(self._base)
        if self._base["schema_version"] == "0.3.0":
            draft["execution_spans"] = deepcopy(self._execution_spans)
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
