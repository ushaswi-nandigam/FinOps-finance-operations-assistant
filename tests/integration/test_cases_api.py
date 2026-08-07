from fastapi.testclient import TestClient
from sqlalchemy import text

from services.api.main import app
from services.common.db import session_scope

client = TestClient(app)


def test_full_pipeline_ingress_to_resolved_case():
    """The whole golden path 1 loop through the HTTP API: ingress a ticket,
    trigger processing, confirm it auto-resolved."""
    with session_scope() as db:
        row = db.execute(text("SELECT ticket_id FROM tickets WHERE intent = 'refund_status_query' LIMIT 1")).mappings().first()
    ticket_id = row["ticket_id"]

    ingress_resp = client.post("/ingress/ticket", json={"ticket_id": ticket_id})
    assert ingress_resp.status_code == 200
    event_id = ingress_resp.json()["event_id"]

    process_resp = client.post("/cases/process", json={"event_id": event_id})
    assert process_resp.status_code == 200
    case = process_resp.json()
    assert case["status"] == "RESOLVE"
    assert case["risk_decision"]["outcome"] == "AUTO_EXECUTE"

    get_resp = client.get(f"/cases/{case['case_id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["case_id"] == case["case_id"]

    list_resp = client.get("/cases", params={"status": "RESOLVE", "limit": 5})
    assert list_resp.status_code == 200
    assert any(c["case_id"] == case["case_id"] for c in list_resp.json())


def test_process_unknown_event_404():
    resp = client.post("/cases/process", json={"event_id": "evt_does_not_exist"})
    assert resp.status_code == 404


def test_get_unknown_case_404():
    resp = client.get("/cases/case_does_not_exist")
    assert resp.status_code == 404
