"""Scoring database — the only place where its SQL is written.

SQL lives in the constants below and parameters are bound by name (`:user_id`)
instead of being interpolated into an f-string: that is both injection safety
and correct type escaping. Every query is logged with its parameters, so a
failing DB check can be reproduced by hand straight from the log.

Connections, pooling and the two cursors come from `BaseDbClient`.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import allure

from api.clients.base_db_client import BaseDbClient, build_engine
from utils.logger import get_logger


if TYPE_CHECKING:
    from collections.abc import Iterator

log = get_logger("db")

# Returned when the user has no stored transaction yet.
NO_DECISION = ""

LAST_DECISION_SQL = """
    SELECT decision FROM transactions
     WHERE user_id = :user_id
     ORDER BY created_at DESC
     LIMIT 1
"""
COUNT_TRANSACTIONS_SQL = "SELECT count(*) FROM transactions WHERE user_id = :user_id"


@contextmanager
def scoring_database(url: str) -> Iterator[ScoringDatabase]:
    """Database for the whole run; the engine and its pool are disposed on exit."""
    engine = build_engine(url)
    try:
        yield ScoringDatabase(engine)
    finally:
        engine.dispose()
        log.info("database engine disposed")


class ScoringDatabase(BaseDbClient):
    """Named queries over the scoring database: no SQL in tests."""

    @allure.step("Read decision of the last transaction from DB")
    def last_decision(self, user_id: str) -> str:
        """Decision of the user's last transaction, blank when there is none."""
        row = self.fetch_one(LAST_DECISION_SQL, {"user_id": user_id})
        decision = str(row[0]) if row and row[0] else NO_DECISION

        log.info("DB decision for user %s: %r", user_id, decision)
        return decision

    @allure.step("Count transactions of a user in DB")
    def count_transactions(self, user_id: str) -> int:
        """How many transactions the database holds for a user."""
        row = self.fetch_one(COUNT_TRANSACTIONS_SQL, {"user_id": user_id})
        count = int(row[0]) if row else 0

        log.info("DB holds %s transaction(s) for user %s", count, user_id)
        return count
