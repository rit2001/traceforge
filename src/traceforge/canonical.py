"""RFC 8785 canonicalization and deterministic SHA-256 helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import rfc8785

from traceforge.exceptions import IntegrityError

JsonObject = dict[str, Any]


def canonicalize(value: Any) -> bytes:
    """Return the RFC 8785 JSON Canonicalization Scheme representation."""
    try:
        return rfc8785.dumps(value)
    except rfc8785.CanonicalizationError as exc:
        raise IntegrityError(f"value cannot be canonicalized with RFC 8785: {exc}") from exc


def sha256_digest(value: Any) -> str:
    """Hash an RFC 8785-canonicalized JSON value."""
    return f"sha256:{hashlib.sha256(canonicalize(value)).hexdigest()}"


def request_fingerprint(request: Any) -> str:
    """Calculate the fingerprint of a sanitized dependency request."""
    return sha256_digest(request)


def capsule_integrity_digest(capsule: Mapping[str, Any]) -> str:
    """Calculate capsule integrity with only ``integrity.digest`` omitted."""
    scoped: JsonObject = dict(capsule)
    integrity = scoped.get("integrity")
    if not isinstance(integrity, Mapping):
        raise IntegrityError("integrity must be an object before calculating its digest")

    scoped_integrity = dict(integrity)
    scoped_integrity.pop("digest", None)
    scoped["integrity"] = scoped_integrity
    return sha256_digest(scoped)
