"""Applies db/schema.sql against the MySQL server in DATABASE_URL.

One plain SQL file instead of a migration framework (Alembic was wired for
Postgres/asyncpg originally) — simplest thing a judge can run and read.
Safe to re-run: every statement is CREATE ... IF NOT EXISTS.
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pymysql

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def _split_statements(sql: str) -> list[str]:
    # No stored procedures / triggers with embedded semicolons in this schema,
    # so a plain split on ';' is enough.
    statements = []
    for raw in sql.split(";"):
        stmt = re.sub(r"--.*", "", raw).strip()
        if stmt:
            statements.append(stmt)
    return statements


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from services.common.config import settings

    url = urlparse(settings.DATABASE_URL.replace("mysql+pymysql://", "mysql://"))
    conn = pymysql.connect(
        host=url.hostname or "localhost",
        port=url.port or 3306,
        user=url.username,
        password=url.password or "",
        charset="utf8mb4",
    )
    try:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            for stmt in _split_statements(sql):
                cur.execute(stmt)
        conn.commit()
        print(f"[OK] Applied {SCHEMA_PATH} to {url.hostname}:{url.port or 3306}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
