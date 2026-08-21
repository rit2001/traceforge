"""TraceForge Replay Capsule validation and sealing."""

__version__ = "0.4.1"

from traceforge.capture import BestEffortRedactionScanner, CaptureSession
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
from traceforge.export import ExportError, export_pytest
from traceforge.replay import ReplayResult, load_runner, replay_exact
from traceforge.sealing import seal_capsule
from traceforge.validation import validate_capsule

__all__ = [
    "__version__",
    "DependencyMismatchError",
    "BestEffortRedactionScanner",
    "CaptureSession",
    "ExportError",
    "IntegrityError",
    "LiveDependencyBlockedError",
    "MissingDependencyError",
    "ReplayResult",
    "SealingError",
    "SemanticValidationError",
    "StructuralValidationError",
    "UnexpectedDependencyError",
    "export_pytest",
    "load_runner",
    "replay_exact",
    "seal_capsule",
    "validate_capsule",
]
