"""Clients a test works with: the scoring API and the scoring database.

Both are session-scoped and hold nothing per test: the HTTP session reuses
connections, and the repository takes a database connection per query and
returns it right away.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from api.clients.base_client import build_session
from api.clients.db_client import scoring_database
from api.clients.scoring_client import ScoringClient
from utils.logger import get_logger


if TYPE_CHECKING:
    from collections.abc import Iterator

    import requests

    from api.clients.db_client import TransactionsRepository
    from utils.config import Config

log = get_logger("fixture")


@pytest.fixture(scope="session")
def http_session(config: Config) -> Iterator[requests.Session]:
    """One HTTP session per run: keep-alive plus shared retries."""
    session = build_session(config)
    try:
        yield session
    finally:
        session.close()
        log.info("HTTP session closed")


@pytest.fixture(scope="session")
def scoring_client(config: Config, http_session: requests.Session) -> ScoringClient:
    """The API client every test talks to."""
    return ScoringClient(config, http_session)


@pytest.fixture(scope="session")
def transactions_repo(config: Config) -> Iterator[TransactionsRepository]:
    """Read access to the scoring database. Skips the test when no URL is set."""
    if not config.db_configured:
        pytest.skip("SCORING_DB_URL is not set: database checks are skipped")

    with scoring_database(config.db_url) as repository:
        yield repository
