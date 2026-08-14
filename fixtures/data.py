"""Test data: what a test needs to exist before it runs, and what to clean up.

Everything created here is deleted in the teardown half of the fixture, so
cleanup also runs when the test fails or the run is interrupted.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from api.clients.scoring_client import ScoringClient
from api.utils.payloads import new_user
from utils.logger import get_logger


log = get_logger("fixture")


@pytest.fixture
def test_data(scoring_client: ScoringClient) -> Iterator[dict[str, Any]]:
    """A user created for one test and deleted afterwards."""
    user_id = scoring_client.create_user_and_get_id(new_user())

    yield {"user_id": user_id}

    log.info("teardown: deleting user %s", user_id)
    scoring_client.delete_user(user_id)


@pytest.fixture
def created_users(scoring_client: ScoringClient) -> Iterator[list[str]]:
    """Registry for users a test creates itself; everything here is deleted afterwards.

    Tests that assert on the creation response need the raw response, so they
    cannot use `test_data` — they register the new id here instead of deleting
    it inline, and cleanup still runs when the test fails later on.
    """
    user_ids: list[str] = []

    yield user_ids

    for user_id in user_ids:
        log.info("teardown: deleting user %s", user_id)
        scoring_client.delete_user(user_id)
