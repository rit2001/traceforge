"""Public exceptions raised by TraceForge's Day 1 implementation."""


class TraceForgeError(Exception):
    """Base class for expected TraceForge failures."""


class StructuralValidationError(TraceForgeError):
    """The capsule does not conform to the Replay Capsule JSON Schema."""


class SemanticValidationError(TraceForgeError):
    """The capsule violates a rule that JSON Schema does not enforce."""


class IntegrityError(TraceForgeError):
    """A request fingerprint or capsule digest does not match its content."""


class SealingError(TraceForgeError):
    """An unsealed draft cannot be converted into a valid sealed capsule."""


class DependencyMismatchError(TraceForgeError):
    """The next actual dependency request does not match its recorded fixture."""


class MissingDependencyError(TraceForgeError):
    """Replay completed before all recorded dependency fixtures were consumed."""


class UnexpectedDependencyError(TraceForgeError):
    """Subject code requested a dependency after recorded fixtures were exhausted."""


class LiveDependencyBlockedError(TraceForgeError):
    """Subject code attempted network access during exact replay."""


class UnsafeToolArgumentsError(TraceForgeError):
    """Tool arguments cannot be persisted without risking request-identity collapse."""


class UnsupportedToolFailureError(TraceForgeError):
    """Exact replay cannot safely reconstruct a recorded tool exception type."""


class UnreplayableCaptureError(TraceForgeError):
    """A completed application run cannot produce legal exact-replay evidence."""


SAFE_TOOL_EXCEPTION_TYPES: dict[str, type[Exception]] = {"TimeoutError": TimeoutError}


def recorded_tool_exception_type(error: Exception) -> str:
    """Return an approved name only when the concrete exception class is exact."""
    for name, exception_type in SAFE_TOOL_EXCEPTION_TYPES.items():
        if type(error) is exception_type:
            return name
    return f"unsupported:{type(error).__name__}"
