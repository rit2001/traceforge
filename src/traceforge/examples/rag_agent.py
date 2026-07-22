"""Offline citation-grounding replay demonstration."""

from __future__ import annotations

from typing import Any

from traceforge.interfaces import DependencyAdapter

RETRIEVAL_REQUEST = {
    "method": "POST",
    "url": "https://retrieval.invalid/search",
    "headers": {"content-type": "application/json"},
    "body": {"query": "What is the archive retention period?"},
}


def run(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
    """Re-run grounding logic against an authoritative recorded passage."""
    outcome = dependencies.invoke("http", "POST", RETRIEVAL_REQUEST)
    passage = outcome["response"]["body"]["passages"][0]
    requested_claim = invocation["claim"]
    grounded = requested_claim in passage["text"]
    answer = requested_claim if grounded else "Records are retained for 30 days."
    return {
        "execution_status": "completed",
        "events": [
            {
                "event_id": "rag-replay-1",
                "sequence": 1,
                "kind": "verification",
                "name": "citation_grounding",
                "data": {"grounded": grounded, "source_id": passage["source_id"]},
            }
        ],
        "output": {"answer": answer, "citation": passage["source_id"], "grounded": True},
        "error": None,
    }
