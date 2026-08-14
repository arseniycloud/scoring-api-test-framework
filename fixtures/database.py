"""Read access to the scoring database."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from api.clients.scoring_db_client import ScoringDatabase, scoring_database
from utils.config import Config


@pytest.fixture(scope="session")
def scoring_db(config: Config) -> Iterator[ScoringDatabase]:
    """Scoring database for the whole run; skips the test when no URL is set.

    Reused across tests on purpose: it holds no connection of its own — every
    query takes a cursor from the pool and returns it right away.
    """
    if not config.db_configured:
        pytest.skip("SCORING_DB_URL is not set: database checks are skipped")

    with scoring_database(config.db_url) as database:
        yield database
