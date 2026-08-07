from services.privacy import vault
from services.privacy.redactor import redact


def test_redacts_pan_and_stores_in_vault(db):
    raw = "My PAN is ABCDE1234F, please verify my KYC."
    redacted, entities = redact(db, raw, "evt_redact_test1")

    assert "ABCDE1234F" not in redacted
    assert "[PAN_1]" in redacted
    assert entities["pan"] == ["[PAN_1]"]

    db.flush()
    assert vault.retrieve(db, "evt_redact_test1__PAN_1") == "ABCDE1234F"


def test_extracts_order_id_and_amount_without_vaulting():
    from services.common.db import session_scope

    with session_scope() as db:
        raw = "Charged ₹2,499 for order #ORD-4471 but it never fulfilled."
        redacted, entities = redact(db, raw, "evt_redact_test2")

    assert "ORD-4471" in redacted  # not PII, left as-is
    assert entities["order_ids"] == ["ORD-4471"]
    assert entities["amounts_inr"] == [2499.0]


def test_multiple_same_type_pii_numbered_sequentially(db):
    raw = "First card 4539578763621486 then second card 4916338506082832."
    redacted, entities = redact(db, raw, "evt_redact_test3")
    assert "[CARD_1]" in redacted
    assert "[CARD_2]" in redacted
    assert entities["card"] == ["[CARD_1]", "[CARD_2]"]


def test_no_pii_passthrough():
    from services.common.db import session_scope

    with session_scope() as db:
        raw = "Where is my refund for order #ORD-1000?"
        redacted, entities = redact(db, raw, "evt_redact_test4")
    assert redacted == raw
    assert "pan" not in entities
