"""Shared pytest fixtures. Tests run against the real local MySQL instance
(scripts/seed.py + scripts/load_seed.py) rather than mocking the DB layer —
simplest way to be honest about what the code actually does."""

import pytest

from services.common.db import session_scope


@pytest.fixture()
def db():
    with session_scope() as session:
        yield session
