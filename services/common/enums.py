from enum import Enum


class Domain(str, Enum):
    SUPPORT = "support"
    PAYMENTS = "payments"
    FRAUD = "fraud"
    INTERNAL_OPS = "internal_ops"
    COMPLIANCE = "compliance"


class RiskTier(str, Enum):
    T0 = "T0"  # Read-only, auto-execute
    T1 = "T1"  # Low risk, auto-execute with sample review
    T2 = "T2"  # Medium risk, single ops approval required
    T3 = "T3"  # High risk, dual approval (maker-checker) required


class Outcome(str, Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    DUAL_APPROVAL = "DUAL_APPROVAL"
    ESCALATE = "ESCALATE"
    DENY = "DENY"


class ActorType(str, Enum):
    AGENT = "agent"
    HUMAN = "human"
    SYSTEM = "system"


class VerifierVerdict(str, Enum):
    PASS = "PASS"
    REVISE = "REVISE"
    REJECT = "REJECT"


class CaseStatus(str, Enum):
    INTAKE = "INTAKE"
    CONTEXT_GATHER = "CONTEXT_GATHER"
    PLAN = "PLAN"
    ACT = "ACT"
    SELF_VERIFY = "SELF_VERIFY"
    RISK_GATE = "RISK_GATE"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    EXECUTE = "EXECUTE"
    RESOLVE = "RESOLVE"
    ESCALATE = "ESCALATE"
