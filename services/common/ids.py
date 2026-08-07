import ulid


def generate_id(prefix: str) -> str:
    """Generate a prefixed ULID string for consistent, chronologically sortable IDs."""
    return f"{prefix}_{ulid.new().str}"


def event_id() -> str:
    return generate_id("evt")


def case_id() -> str:
    return generate_id("case")


def decision_id() -> str:
    return generate_id("dec")


def proposal_id() -> str:
    return generate_id("prop")


def trace_id() -> str:
    return generate_id("trc")


def customer_token() -> str:
    return generate_id("cus_tok")
