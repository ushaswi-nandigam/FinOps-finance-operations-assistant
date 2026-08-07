from services.audit.ledger import get_case_decisions, record_decision, verify_chain
from services.common.ids import generate_id
from services.common.schemas import ActorRecord, CostRecord


def _actor(name="payments_agent"):
    return ActorRecord(type="agent", name=name, model="gemini-2.0-flash-lite", version="v0.1")


def test_record_decision_returns_populated_record(db):
    case_id = generate_id("case")
    d = record_decision(
        db, case_id=case_id, actor=_actor(), action={"type": "issue_refund", "amount_inr": 2499},
        outcome="NEEDS_APPROVAL", reason_plain="Refund between ₹500 and ₹25,000 requires approval.",
        evidence=[{"type": "transaction", "ref": "txn_1"}], matched_rules=["REFUND-POL-3.2"],
        verifier={"verdict": "PASS"}, cost=CostRecord(stage="tier2_llm", tokens_in=100, tokens_out=20, inr=0.05),
        policy_version="2026.08.01",
    )
    assert d.decision_id.startswith("dec_")
    assert d.case_id == case_id
    assert d.seq == 1
    assert d.entry_hash != d.prev_hash
    assert len(d.entry_hash) == 64


def test_case_seq_increments_per_case(db):
    case_id = generate_id("case")
    d1 = record_decision(db, case_id=case_id, actor=_actor(), action={"a": 1}, outcome="AUTO_EXECUTE",
                          reason_plain="first", policy_version="2026.08.01")
    d2 = record_decision(db, case_id=case_id, actor=_actor(), action={"a": 2}, outcome="AUTO_EXECUTE",
                          reason_plain="second", policy_version="2026.08.01")
    assert d1.seq == 1
    assert d2.seq == 2
    assert d2.prev_hash == d1.entry_hash


def test_hash_chain_links_across_different_cases(db):
    """The chain is global: two unrelated cases still link sequentially."""
    case_a, case_b = generate_id("case"), generate_id("case")
    d1 = record_decision(db, case_id=case_a, actor=_actor(), action={}, outcome="AUTO_EXECUTE",
                          reason_plain="a1", policy_version="2026.08.01")
    d2 = record_decision(db, case_id=case_b, actor=_actor(), action={}, outcome="ESCALATE",
                          reason_plain="b1", policy_version="2026.08.01")
    assert d2.prev_hash == d1.entry_hash


def test_escalation_recorded_with_same_rigour_as_action(db):
    """The brief explicitly requires escalations to be logged as rigorously
    as actions — same function, same fields, nothing optional skipped."""
    case_id = generate_id("case")
    d = record_decision(
        db, case_id=case_id, actor=_actor("fraud_agent"), action={"type": "none", "reason": "escalated"},
        outcome="ESCALATE", reason_plain="Confidence below threshold; escalating for human review.",
        matched_rules=["CONFIDENCE-GATE-1"], policy_version="2026.08.01",
    )
    assert d.outcome == "ESCALATE"
    assert d.reason_plain != ""
    assert d.entry_hash != ""


def test_get_case_decisions_ordered_by_case_seq(db):
    case_id = generate_id("case")
    for i in range(3):
        record_decision(db, case_id=case_id, actor=_actor(), action={"i": i}, outcome="AUTO_EXECUTE",
                         reason_plain=f"step {i}", policy_version="2026.08.01")
    rows = get_case_decisions(db, case_id)
    assert [r["case_seq"] for r in rows] == [1, 2, 3]


def test_verify_chain_valid_on_untampered_ledger(db):
    case_id = generate_id("case")
    record_decision(db, case_id=case_id, actor=_actor(), action={}, outcome="AUTO_EXECUTE",
                     reason_plain="ok", policy_version="2026.08.01")
    report = verify_chain(db)
    assert report["valid"] is True


def test_verify_chain_detects_tampering(db):
    """Tampers with a row, confirms detection, then restores the original
    value — this ledger is a real, persistent MySQL table shared across test
    runs, so leaving it corrupted would break every later test that calls
    verify_chain()."""
    from sqlalchemy import text

    case_id = generate_id("case")
    d = record_decision(db, case_id=case_id, actor=_actor(), action={}, outcome="AUTO_EXECUTE",
                         reason_plain="original reason", policy_version="2026.08.01")
    db.flush()
    db.execute(text("UPDATE decision_records SET reason_plain = 'tampered!' WHERE decision_id = :id"), {"id": d.decision_id})
    db.flush()
    report = verify_chain(db)
    assert report["valid"] is False

    db.execute(text("UPDATE decision_records SET reason_plain = :orig WHERE decision_id = :id"),
               {"orig": "original reason", "id": d.decision_id})
    db.flush()
    restored = verify_chain(db)
    assert restored["valid"] is True
