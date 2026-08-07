"""L2 — normalisation & de-identification.

`redact()` is the one function every piece of raw customer text must pass
through before it reaches a prompt, a log line, or a stored event. Real PII
values are written to the encrypted vault (services/privacy/vault.py) keyed
by a token that is namespaced to the source event, so `[PAN_1]` in two
different tickets never collides in the vault.
"""

import re
from collections import defaultdict

from sqlalchemy.orm import Session

from services.privacy import vault
from services.privacy.recognizers import find_pii

ORDER_ID_RE = re.compile(r"\bORD-\d{3,6}\b")
TXN_ID_RE = re.compile(r"\btxn_\d{3,10}\b")
AMOUNT_RE = re.compile(r"₹\s?([\d,]+(?:\.\d{1,2})?)")


def redact(db: Session, raw_text: str, ref_id: str) -> tuple[str, dict[str, list[str]]]:
    """Returns (redacted_text, entities). Writes real PII values to the vault
    as a side effect. `ref_id` (an event_id or trace_id) namespaces the
    vault tokens for this piece of text."""
    matches = find_pii(raw_text)

    counters: dict[str, int] = defaultdict(int)
    redacted_parts: list[str] = []
    last_idx = 0
    pii_entities: dict[str, list[str]] = defaultdict(list)

    for m in matches:
        counters[m.label] += 1
        placeholder = f"[{m.label}_{counters[m.label]}]"
        vault_token = f"{ref_id}__{m.label}_{counters[m.label]}"

        redacted_parts.append(raw_text[last_idx:m.start])
        redacted_parts.append(placeholder)
        last_idx = m.end

        vault.store(db, vault_token, m.label, m.value)
        pii_entities[m.label.lower()].append(placeholder)

    redacted_parts.append(raw_text[last_idx:])
    redacted_text = "".join(redacted_parts)

    entities: dict[str, list[str]] = dict(pii_entities)
    order_ids = ORDER_ID_RE.findall(redacted_text)
    if order_ids:
        entities["order_ids"] = order_ids
    txn_ids = TXN_ID_RE.findall(redacted_text)
    if txn_ids:
        entities["txn_ids"] = txn_ids
    amounts = AMOUNT_RE.findall(redacted_text)
    if amounts:
        entities["amounts_inr"] = [float(a.replace(",", "")) for a in amounts]

    return redacted_text, entities
