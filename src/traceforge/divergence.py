"""Evidence-backed analysis derived from a completed portable execution diff."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from traceforge.canonical import canonicalize
from traceforge.diff import ExecutionDiff
from traceforge.exceptions import IntegrityError

_DOMAINS = ("execution", "dependencies", "events", "terminal")
_DOMAIN_FINDINGS = {
    "execution": "execution_diverged",
    "dependencies": "dependency_stream_diverged",
    "events": "event_stream_diverged",
    "terminal": "terminal_output_diverged",
}
_LIMITATIONS = (
    "no_global_chronology",
    "no_root_cause_claim",
    "no_cross_domain_causality",
)
_SUMMARY_FIELDS = {"format_version", "matches", "sections", "first_divergences"}
_SECTION_FIELDS = {"matches", "difference_count"}
_DOMAIN_PATH_ROOTS = {
    "execution": ("/execution_status", "/error"),
    "dependencies": ("/dependencies",),
    "events": ("/events",),
    "terminal": ("/output",),
}


@dataclass(frozen=True, init=False)
class DivergenceAnalysis:
    """Alias-isolated, versioned summary of one completed ``ExecutionDiff``."""

    _canonical_document: bytes = field(repr=False)

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("DivergenceAnalysis values are created by analyze_divergence")

    @classmethod
    def _from_canonical_document(cls, document: bytes) -> DivergenceAnalysis:
        instance = object.__new__(cls)
        object.__setattr__(instance, "_canonical_document", document)
        return instance

    def to_dict(self) -> dict[str, Any]:
        """Return a newly allocated JSON-compatible representation."""
        document = json.loads(self._canonical_document)
        if not isinstance(document, dict):  # pragma: no cover - construction invariant
            raise IntegrityError("DivergenceAnalysis must contain a JSON object")
        return document

    def canonical_bytes(self) -> bytes:
        """Return the immutable RFC 8785 serialization of this analysis."""
        return bytes(self._canonical_document)


def _domain_document(document: dict[str, Any], name: str) -> dict[str, Any]:
    try:
        section = document["sections"][name]
        first_path = document["first_divergences"][name]
        matches = section["matches"]
        difference_count = section["difference_count"]
    except (KeyError, TypeError) as exc:
        raise IntegrityError(f"ExecutionDiff is missing the {name!r} domain contract") from exc

    if not isinstance(section, dict) or set(section) != _SECTION_FIELDS:
        raise IntegrityError(
            f"ExecutionDiff {name!r} section must contain exactly the supported fields"
        )
    if not isinstance(matches, bool):
        raise IntegrityError(f"ExecutionDiff {name!r} matches value must be boolean")
    if (
        not isinstance(difference_count, int)
        or isinstance(difference_count, bool)
        or difference_count < 0
    ):
        raise IntegrityError(
            f"ExecutionDiff {name!r} difference_count must be a non-negative integer"
        )
    if first_path is not None and (
        not isinstance(first_path, str) or not first_path.startswith("/")
    ):
        raise IntegrityError(f"ExecutionDiff {name!r} first divergence must be a path or null")
    if first_path is not None and not any(
        first_path == root or first_path.startswith(f"{root}/") for root in _DOMAIN_PATH_ROOTS[name]
    ):
        raise IntegrityError(f"ExecutionDiff {name!r} first divergence uses the wrong domain path")
    if matches != (difference_count == 0):
        raise IntegrityError(f"ExecutionDiff {name!r} match summary is inconsistent")
    if matches != (first_path is None):
        raise IntegrityError(f"ExecutionDiff {name!r} first divergence is inconsistent")
    return {
        "matches": matches,
        "difference_count": difference_count,
        "first_path": first_path,
    }


def _analyze_divergence(
    execution_diff: ExecutionDiff, *, exact_replay_completed: bool
) -> DivergenceAnalysis:
    if not isinstance(execution_diff, ExecutionDiff):
        raise TypeError("execution_diff must be an ExecutionDiff")

    source = execution_diff._analysis_summary()
    if set(source) != _SUMMARY_FIELDS:
        raise IntegrityError("ExecutionDiff analysis metadata has an unsupported contract shape")
    if source.get("format_version") != "0.1.0":
        raise IntegrityError("DivergenceAnalysis 0.1.0 requires ExecutionDiff 0.1.0")
    sections = source.get("sections")
    first_divergences = source.get("first_divergences")
    if not isinstance(sections, dict) or set(sections) != set(_DOMAINS):
        raise IntegrityError("ExecutionDiff sections must contain exactly the supported domains")
    if not isinstance(first_divergences, dict) or set(first_divergences) != set(_DOMAINS):
        raise IntegrityError(
            "ExecutionDiff first_divergences must contain exactly the supported domains"
        )
    domains = {name: _domain_document(source, name) for name in _DOMAINS}
    matches = source.get("matches")
    if not isinstance(matches, bool) or matches != all(
        domain["matches"] for domain in domains.values()
    ):
        raise IntegrityError("ExecutionDiff overall match summary is inconsistent")

    dependencies_reproduced = exact_replay_completed and domains["dependencies"]["matches"]
    findings: list[str] = []
    if dependencies_reproduced:
        findings.append("recorded_dependencies_reproduced")
    if matches:
        findings.append("no_semantic_divergence")
    else:
        findings.extend(_DOMAIN_FINDINGS[name] for name in _DOMAINS if not domains[name]["matches"])

    document = {
        "format_version": "0.1.0",
        "matches": matches,
        "domains": domains,
        "evidence_context": {
            "recorded_dependencies_reproduced": dependencies_reproduced,
            "replay_completed_technically": exact_replay_completed,
        },
        "findings": findings,
        "limitations": list(_LIMITATIONS),
    }
    return DivergenceAnalysis._from_canonical_document(canonicalize(document))


def analyze_divergence(execution_diff: ExecutionDiff) -> DivergenceAnalysis:
    """Derive only facts contained in a completed portable execution diff."""
    return _analyze_divergence(execution_diff, exact_replay_completed=False)


def _analyze_exact_replay_divergence(execution_diff: ExecutionDiff) -> DivergenceAnalysis:
    """Attach context available only after successful exact replay orchestration."""
    return _analyze_divergence(execution_diff, exact_replay_completed=True)
