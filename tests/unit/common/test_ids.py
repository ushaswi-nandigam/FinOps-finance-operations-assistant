from services.common.ids import (
    case_id,
    customer_token,
    decision_id,
    event_id,
    proposal_id,
    trace_id,
)


def test_id_prefixes():
    assert event_id().startswith("evt_")
    assert case_id().startswith("case_")
    assert decision_id().startswith("dec_")
    assert proposal_id().startswith("prop_")
    assert trace_id().startswith("trc_")
    assert customer_token().startswith("cus_tok_")


def test_id_uniqueness():
    ids = {case_id() for _ in range(100)}
    assert len(ids) == 100
