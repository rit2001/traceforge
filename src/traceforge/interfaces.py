"""Protocols used by the current exact-replay vertical slice."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class RedactionScanner(Protocol):
    """Best-effort sanitization performed before captured data is persisted."""

    policy_version: str

    def scan(self, value: Any, path: str = "$") -> Any: ...


class DependencyAdapter(Protocol):
    """Supplies deterministic recorded outcomes to subject code."""

    def invoke(self, kind: str, operation: str, request: Any) -> dict[str, Any]: ...

    def assert_consumed(self) -> None: ...


class CapsuleStore(Protocol):
    """Loads and saves local JSON artifacts used by the current CLI."""

    def load(self, path: Path) -> Any: ...

    def save(self, path: Path, value: Any) -> None: ...


class FrameworkAdapter(Protocol):
    """Runs trusted local subject code with injected recorded dependencies."""

    def run(self, invocation_input: Any, dependencies: DependencyAdapter) -> dict[str, Any]: ...
