"""TraceForge Replay Capsule validation and sealing."""

__version__ = "0.4.1"

from traceforge.capture import BestEffortRedactionScanner, CaptureSession
from traceforge.dependencies import invoke_recorded_tool
from traceforge.divergence import DivergenceAnalysis, analyze_divergence
from traceforge.exceptions import (
    DependencyMismatchError,
    IntegrityError,
    LiveDependencyBlockedError,
    MissingDependencyError,
    SealingError,
    SemanticValidationError,
    StructuralValidationError,
    UnexpectedDependencyError,
    UnreplayableCaptureError,
    UnsafeToolArgumentsError,
    UnsupportedToolFailureError,
)
from traceforge.export import ExportError, export_pytest
from traceforge.interfaces import DependencyAdapter
from traceforge.replay import ReplayResult, load_runner, replay_exact
from traceforge.sealing import seal_capsule
from traceforge.validation import validate_capsule

__all__ = [
    "__version__",
    "DependencyMismatchError",
    "DependencyAdapter",
    "DivergenceAnalysis",
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
    "UnreplayableCaptureError",
    "UnexpectedDependencyError",
    "UnsafeToolArgumentsError",
    "UnsupportedToolFailureError",
    "export_pytest",
    "analyze_divergence",
    "load_runner",
    "invoke_recorded_tool",
    "replay_exact",
    "seal_capsule",
    "validate_capsule",
]
