"""Offline consequential tool-argument replay demonstration."""

from __future__ import annotations

from typing import Any

from traceforge.interfaces import DependencyAdapter


def refund_request(invocation: Any) -> dict[str, Any]:
    return {
        "method": "POST",
        "url": "https://payments.invalid/refunds",
        "headers": {"content-type": "application/json"},
        "body": {
            "customer_ref": invocation["customer_ref"],
            "amount_cents": invocation["amount_cents"],
            "currency": "USD",
        },
    }


def run(invocation: Any, dependencies: DependencyAdapter) -> dict[str, Any]:
    """Execute only the exact recorded sanitized refund request."""
    outcome = dependencies.invoke("http", "POST", refund_request(invocation))
    response = outcome["response"]["body"]
    return {
        "execution_status": "completed",
        "events": [
            {
                "event_id": "refund-replay-1",
                "sequence": 1,
                "kind": "tool",
                "name": "refund_approval",
                "data": {"decision": response["decision"]},
            }
        ],
        "output": response,
        "error": None,
    }
