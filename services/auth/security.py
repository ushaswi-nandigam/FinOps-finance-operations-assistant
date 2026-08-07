"""Hand-rolled JWT + bcrypt auth (docs/architecture.md §L13's RBAC roles:
viewer/ops_agent/approver/supervisor/auditor). No Supabase Auth available in
this stack (see docs/LEARN.md) — this is the minimal thing that gets a real
login, a role on the token, and a stable user identity for the maker!=checker
DB constraint on approvals to enforce against.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.common.config import settings
from services.common.ids import generate_id


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_user(db: Session, *, username: str, password: str, role: str) -> dict[str, Any]:
    user_id = generate_id("usr")
    db.execute(
        text("""INSERT INTO users (user_id, username, password_hash, role, created_at)
                VALUES (:id, :username, :hash, :role, :created_at)
                ON DUPLICATE KEY UPDATE password_hash = :hash, role = :role"""),
        {"id": user_id, "username": username, "hash": hash_password(password), "role": role,
         "created_at": datetime.now(timezone.utc)},
    )
    return {"user_id": user_id, "username": username, "role": role}


def authenticate(db: Session, *, username: str, password: str) -> dict[str, Any] | None:
    row = db.execute(text("SELECT * FROM users WHERE username = :u"), {"u": username}).mappings().first()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    return {"user_id": row["user_id"], "username": row["username"], "role": row["role"]}


def create_access_token(user: dict[str, Any]) -> str:
    payload = {
        "sub": user["username"], "user_id": user["user_id"], "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, settings.APPROVAL_JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.APPROVAL_JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
