"""The API client a test talks to."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from api.clients.scoring_client import scoring_api


if TYPE_CHECKING:
    from collections.abc import Iterator

    from api.clients.scoring_client import ScoringClient
    from utils.config import Config


@pytest.fixture(scope="session")
def scoring_client(config: Config) -> Iterator[ScoringClient]:
    """Scoring API client for the whole run; its HTTP session is closed at the end."""
    with scoring_api(config) as client:
        yield client
