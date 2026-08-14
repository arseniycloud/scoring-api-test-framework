"""Run fixtures: config -> session -> clients -> test data.

Cleanup lives in the teardown part of a fixture, so it runs when a test fails
and when the run is interrupted. Fixtures log what they build and what they
clean up, so a log read top to bottom shows the lifecycle of every test.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

import pytest

from api.clients.base_client import build_session
from api.clients.db_client import scoring_database
from api.clients.scoring_client import ScoringClient
from api.utils.payloads import new_user
from utils.config import Config
from utils.logger import get_logger, mask_secrets, silence_noisy_loggers


if TYPE_CHECKING:
    from collections.abc import Iterator

    import requests

    from api.clients.db_client import TransactionsRepository

log = get_logger("fixture")


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001 — pytest hook signature
    """Runs before collection: keep third-party DEBUG noise out of our log."""
    silence_noisy_loggers()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--scoring-base-url",
        action="store",
        default="",
        help="Base URL of the scoring service (overrides SCORING_BASE_URL)",
    )


@pytest.fixture(scope="session")
def config(request: pytest.FixtureRequest) -> Config:
    """Config from the environment; `--scoring-base-url` wins over env."""
    base_config = Config.from_env()
    cli_base_url = request.config.getoption("--scoring-base-url")
    if cli_base_url:
        base_config = replace(base_config, base_url=cli_base_url.rstrip("/"))

    log.info("run config: base_url=%s db_configured=%s", base_config.base_url, base_config.db_configured)
    log.debug("full config: %s", mask_secrets(str(base_config)))
    return base_config


@pytest.fixture(scope="session")
def http_session(config: Config) -> Iterator[requests.Session]:
    """One session per run: keep-alive plus shared retries."""
    session = build_session(config)
    try:
        yield session
    finally:
        session.close()
        log.info("HTTP session closed")


@pytest.fixture(scope="session")
def scoring_client(config: Config, http_session: requests.Session) -> ScoringClient:
    return ScoringClient(config, http_session)


@pytest.fixture(scope="session")
def transactions_repo(config: Config) -> Iterator[TransactionsRepository]:
    """Database repository for the run. Without a URL the db tests are skipped.

    Session-scoped on purpose: the repository holds no connection of its own,
    each query takes one from the pool and returns it, so nothing leaks between
    tests and there is no per-test setup to pay for.
    """
    if not config.db_configured:
        log.warning("SCORING_DB_URL is not set: skipping the database checks")
        pytest.skip("SCORING_DB_URL is not set: database checks are skipped")

    with scoring_database(config.db_url) as repository:
        yield repository


@pytest.fixture
def test_data(scoring_client: ScoringClient) -> Iterator[dict[str, Any]]:
    """Per-test data: a created user that is deleted in teardown."""
    user_id = scoring_client.create_user_and_get_id(new_user())

    yield {"user_id": user_id}

    log.info("teardown: deleting user %s", user_id)
    scoring_client.delete_user(user_id)


@pytest.fixture
def created_users(scoring_client: ScoringClient) -> Iterator[list[str]]:
    """Registry for users a test creates itself: everything here is deleted in teardown.

    Tests that assert on the creation response need the raw response, so they
    cannot use `test_data` — they register the new id here instead of deleting
    it inline, and cleanup still runs when the test fails later on.
    """
    user_ids: list[str] = []

    yield user_ids

    for user_id in user_ids:
        log.info("teardown: deleting user %s", user_id)
        scoring_client.delete_user(user_id)
