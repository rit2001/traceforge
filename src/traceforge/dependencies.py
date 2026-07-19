"""Fail-closed recorded dependency playback."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from traceforge.canonical import request_fingerprint
from traceforge.exceptions import (
    DependencyMismatchError,
    MissingDependencyError,
    UnexpectedDependencyError,
)


class RecordedDependencyAdapter:
    """Consume recorded outcomes in order without any live fallback path."""

    def __init__(self, recorded: list[dict[str, Any]]) -> None:
        self._recorded = deepcopy(recorded)
        self._index = 0

    @property
    def consumed(self) -> int:
        return self._index

    def invoke(self, kind: str, operation: str, request: Any) -> dict[str, Any]:
        if self._index >= len(self._recorded):
            raise UnexpectedDependencyError(
                f"unexpected {kind} dependency at sequence {self._index + 1}; "
                "no recorded fixture remains"
            )

        recorded = self._recorded[self._index]
        sequence = self._index + 1
        if kind != recorded["kind"]:
            raise DependencyMismatchError(
                f"dependency {sequence} kind mismatch: expected {recorded['kind']!r}, got {kind!r}"
            )
        if operation != recorded["operation"]:
            raise DependencyMismatchError(
                f"dependency {sequence} operation mismatch: "
                f"expected {recorded['operation']!r}, got {operation!r}"
            )

        actual_fingerprint = request_fingerprint(request)
        if actual_fingerprint != recorded["request_fingerprint"]:
            raise DependencyMismatchError(
                f"dependency {sequence} request mismatch for {kind} {operation}; "
                "sanitized request fingerprint differs from the recorded fixture"
            )

        self._index += 1
        return deepcopy(recorded["outcome"])

    def assert_consumed(self) -> None:
        if self._index != len(self._recorded):
            next_recorded = self._recorded[self._index]
            raise MissingDependencyError(
                f"missing dependency call at sequence {self._index + 1}: "
                f"expected {next_recorded['kind']} {next_recorded['operation']}"
            )
