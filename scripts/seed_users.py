"""Creates demo login accounts for the React console, one per RBAC role
(docs/architecture.md §L13). Passwords are demo-only — change before any
real deployment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.auth.security import create_user  # noqa: E402
from services.common.db import session_scope  # noqa: E402

DEMO_USERS = [
    ("viewer1", "demo1234", "viewer"),
    ("ops1", "demo1234", "ops_agent"),
    ("approver_alice", "demo1234", "approver"),
    ("approver_bob", "demo1234", "approver"),
    ("supervisor1", "demo1234", "supervisor"),
    ("auditor1", "demo1234", "auditor"),
]


def main() -> None:
    with session_scope() as db:
        for username, password, role in DEMO_USERS:
            create_user(db, username=username, password=password, role=role)
    print(f"[OK] Seeded {len(DEMO_USERS)} demo users (password 'demo1234' for all).")


if __name__ == "__main__":
    main()
