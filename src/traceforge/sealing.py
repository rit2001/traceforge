"""Creation of sealed Replay Capsules from unsealed drafts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from traceforge.canonical import capsule_integrity_digest, request_fingerprint
from traceforge.exceptions import SealingError, TraceForgeError
from traceforge.validation import validate_capsule

INTEGRITY_METADATA = {
    "algorithm": "sha256",
    "canonicalization": "RFC8785",
    "scope": "entire_capsule_except_integrity.digest",
}


def seal_capsule(draft: Any) -> dict[str, Any]:
    """Return a new sealed capsule, ignoring caller-derived integrity fields."""
    if not isinstance(draft, dict):
        raise SealingError("capsule draft must be a JSON object")

    sealed = deepcopy(draft)
    try:
        dependencies = sealed.get("dependencies")
        if not isinstance(dependencies, list):
            raise SealingError("capsule draft must contain a dependencies array")
        for index, dependency in enumerate(dependencies):
            if not isinstance(dependency, dict) or "request" not in dependency:
                raise SealingError(f"dependencies.{index} must contain a request object")
            dependency["request_fingerprint"] = request_fingerprint(dependency["request"])

        sealed["integrity"] = dict(INTEGRITY_METADATA)
        sealed["integrity"]["digest"] = capsule_integrity_digest(sealed)
        validate_capsule(sealed)
    except SealingError:
        raise
    except TraceForgeError as exc:
        raise SealingError(f"cannot seal capsule draft: {exc}") from exc
    return sealed
