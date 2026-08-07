from fastapi.testclient import TestClient

from services.api.main import app
from services.audit.ledger import record_decision
from services.common.db import session_scope
from services.common.ids import generate_id
from services.common.schemas import ActorRecord

client = TestClient(app)


def test_audit_export_unknown_case_404():
    resp = client.get("/audit/export", params={"case_id": "case_does_not_exist"})
    assert resp.status_code == 404


def test_audit_export_returns_signed_payload():
    case_id = generate_id("case")
    with session_scope() as db:
        record_decision(
            db, case_id=case_id, actor=ActorRecord(type="agent", name="support_agent"),
            action={"type": "send_templated_reply"}, outcome="AUTO_EXECUTE",
            reason_plain="Answered a routine status query.", policy_version="2026.08.01",
        )

    resp = client.get("/audit/export", params={"case_id": case_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"] == case_id
    assert body["decision_count"] == 1
    assert body["ledger_integrity"]["valid"] is True
    assert "signature" in body and len(body["signature"]) == 64


def test_audit_verify_endpoint():
    resp = client.get("/audit/verify")
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
