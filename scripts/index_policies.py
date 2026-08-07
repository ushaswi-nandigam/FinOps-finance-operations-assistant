"""Embeds every policy clause for the Compliance Agent's RAG search
(services/orchestrator/agents/compliance.py). Re-runnable: upserts by
policy_id, so it's safe after `make seed && make load-seed` regenerates the
policies table."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.common.db import session_scope  # noqa: E402
from services.orchestrator.agents.compliance import index_policies  # noqa: E402


def main() -> None:
    with session_scope() as db:
        n = index_policies(db)
    print(f"[OK] Indexed {n} policy clauses for compliance search.")


if __name__ == "__main__":
    main()
