from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from traceforge.dependencies import RecordedDependencyAdapter
from traceforge.examples.rag_agent import run as rag_runner
from traceforge.examples.tool_safety_agent import refund_request
from traceforge.examples.tool_safety_agent import run as tool_safety_runner
from traceforge.exceptions import DependencyMismatchError
from traceforge.replay import CallableFrameworkAdapter, replay_exact

ROOT = Path(__file__).resolve().parents[1]


def _load(case: str, name: str) -> dict:
    return json.loads((ROOT / "examples" / case / name).read_text(encoding="utf-8"))


def test_rag_replay_corrects_grounding_without_mutating_evidence() -> None:
    capsule = _load("rag-citation", "replay-capsule.json")
    original = copy.deepcopy(capsule)
    result = replay_exact(
        capsule,
        CallableFrameworkAdapter(rag_runner),
        _load("rag-citation", "regression-spec.json"),
    )
    assert result.regression is not None and result.regression.passed
    assert result.replay_observation["output"]["grounded"] is True
    assert result.original_observation["output"]["grounded"] is False
    assert capsule == original


def test_tool_safety_replay_and_changed_argument_fail_closed() -> None:
    capsule = _load("tool-argument-safety", "replay-capsule.json")
    result = replay_exact(
        capsule,
        CallableFrameworkAdapter(tool_safety_runner),
        _load("tool-argument-safety", "regression-spec.json"),
    )
    assert result.regression is not None and result.regression.passed

    changed = copy.deepcopy(capsule["invocation"]["input"])
    changed["amount_cents"] += 1
    adapter = RecordedDependencyAdapter(capsule["dependencies"])
    with pytest.raises(DependencyMismatchError, match="request mismatch"):
        adapter.invoke("http", "POST", refund_request(changed))
    assert adapter.consumed == 0
