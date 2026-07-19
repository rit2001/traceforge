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
