"""TraceForge Replay Capsule validation and sealing."""

from traceforge.exceptions import (
    DependencyMismatchError,
    IntegrityError,
    LiveDependencyBlockedError,
    MissingDependencyError,
    SealingError,
    SemanticValidationError,
    StructuralValidationError,
    UnexpectedDependencyError,
)
from traceforge.replay import ReplayResult, replay_exact
from traceforge.sealing import seal_capsule
from traceforge.validation import validate_capsule

__all__ = [
    "DependencyMismatchError",
    "IntegrityError",
    "LiveDependencyBlockedError",
    "MissingDependencyError",
    "ReplayResult",
    "SealingError",
    "SemanticValidationError",
    "StructuralValidationError",
    "UnexpectedDependencyError",
    "replay_exact",
    "seal_capsule",
    "validate_capsule",
]
