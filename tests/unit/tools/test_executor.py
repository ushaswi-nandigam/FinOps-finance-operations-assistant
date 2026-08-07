from sqlalchemy import text

from services.common.ids import generate_id
from services.tools.executor import execute_tool


def _sample_txn(db):
    return db.execute(text("SELECT txn_id, amount_inr, customer_ref FROM transactions LIMIT 1")).mappings().first()


def test_dry_run_does_not_write_to_tool_calls(db):
    txn = _sample_txn(db)
    case_id = generate_id("case")
    result = execute_tool(db, case_id=case_id, tool_name="issue_refund",
                           args={"txn_id": txn["txn_id"], "amount_inr": float(txn["amount_inr"])}, dry_run=True)
    assert result["ok"] is True
    assert result["dry_run"] is True

    db.flush()
    count = db.execute(text("SELECT COUNT(*) AS c FROM tool_calls WHERE case_id = :cid"), {"cid": case_id}).mappings().first()
    assert count["c"] == 0


def test_real_execution_recorded_and_idempotent_replay(db):
    txn = _sample_txn(db)
    case_id = generate_id("case")
    args = {"txn_id": txn["txn_id"], "amount_inr": float(txn["amount_inr"])}

    first = execute_tool(db, case_id=case_id, tool_name="issue_refund", args=args, dry_run=False)
    assert first["ok"] is True
    assert "idempotent_replay" not in first

    db.flush()
    count = db.execute(text("SELECT COUNT(*) AS c FROM tool_calls WHERE case_id = :cid"), {"cid": case_id}).mappings().first()
    assert count["c"] == 1

    # Double-click "Approve": same case_id + tool + args must not execute
    # twice or insert a second tool_calls row (idempotency_key UNIQUE).
    second = execute_tool(db, case_id=case_id, tool_name="issue_refund", args=args, dry_run=False)
    assert second["idempotent_replay"] is True

    db.flush()
    count_after = db.execute(text("SELECT COUNT(*) AS c FROM tool_calls WHERE case_id = :cid"), {"cid": case_id}).mappings().first()
    assert count_after["c"] == 1


def test_different_case_same_args_not_treated_as_duplicate(db):
    txn = _sample_txn(db)
    args = {"txn_id": txn["txn_id"], "amount_inr": float(txn["amount_inr"])}
    case_a, case_b = generate_id("case"), generate_id("case")

    r1 = execute_tool(db, case_id=case_a, tool_name="issue_refund", args=args, dry_run=False)
    r2 = execute_tool(db, case_id=case_b, tool_name="issue_refund", args=args, dry_run=False)
    assert "idempotent_replay" not in r1
    assert "idempotent_replay" not in r2


def test_unknown_tool_raises():
    import pytest
    from services.common.db import session_scope

    with pytest.raises(ValueError):
        with session_scope() as db:
            execute_tool(db, case_id="case_x", tool_name="not_a_real_tool", args={}, dry_run=True)


def test_t0_action_no_idempotency_key_required(db):
    """tag_ticket has requires_idempotency=False — repeated calls just run
    again, which is correct since tagging is naturally idempotent already."""
    result = execute_tool(db, case_id=generate_id("case"), tool_name="tag_ticket",
                           args={"ticket_id": "tkt_1000", "tag": "refund_status_query"}, dry_run=False)
    assert result["ok"] is True
