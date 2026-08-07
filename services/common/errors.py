class FinOpsException(Exception):
    """Base exception class for Agentic FinOps Assistant."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SchemaValidationError(FinOpsException):
    """Raised when data contracts or schema invariants are violated."""
    pass


class PIIViolationError(FinOpsException):
    """Raised when un-redacted PII is attempted to be passed downstream of Layer 2."""
    pass


class PolicyEngineError(FinOpsException):
    """Raised when policy evaluation fails or encounters an unhandled rule invariant."""
    pass


class ExecutionError(FinOpsException):
    """Raised when tool or saga execution fails."""
    pass


class IdempotencyError(FinOpsException):
    """Raised when a duplicated side-effecting action is detected."""
    pass


class BudgetExceededError(FinOpsException):
    """Raised when token or financial spend budget for a case is exceeded."""
    pass


class EscalationRequired(FinOpsException):
    """Raised when an explicit escalation state must be triggered."""
    pass
