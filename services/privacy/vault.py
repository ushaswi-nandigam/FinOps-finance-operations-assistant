"""AES-GCM encrypted PII vault. Real values never leave this module except
at a tool's execution boundary (services/tools) — everything upstream of
that (triage, agents, verifier, policy engine) only ever sees a token like
`[PAN_1]`.
"""

import base64
import hashlib
import os
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.common.config import settings


def _key() -> bytes:
    # Accept any-length passphrase from config/env; always derive a proper
    # 32-byte AES-256 key from it rather than requiring an exact-length secret.
    return hashlib.sha256(settings.PII_VAULT_AES_KEY.encode("utf-8")).digest()


def encrypt(plaintext: str) -> str:
    aesgcm = AESGCM(_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt(blob: str) -> str:
    raw = base64.b64decode(blob)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(_key())
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def store(db: Session, token: str, field_type: str, plaintext_value: str) -> None:
    db.execute(
        text("""INSERT INTO pii_vault (token, field_type, encrypted_value, created_at)
                VALUES (:token, :field_type, :value, :created_at)
                ON DUPLICATE KEY UPDATE encrypted_value = :value"""),
        {
            "token": token, "field_type": field_type,
            "value": encrypt(plaintext_value), "created_at": datetime.now(timezone.utc),
        },
    )


def retrieve(db: Session, token: str) -> str | None:
    """Detokenise. Only ever called from services/tools at the execution
    boundary, for fields a tool genuinely needs — never from an agent prompt
    or the policy engine."""
    row = db.execute(text("SELECT encrypted_value FROM pii_vault WHERE token = :token"), {"token": token}).mappings().first()
    if not row:
        return None
    return decrypt(row["encrypted_value"])
