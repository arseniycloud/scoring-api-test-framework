"""Access to the scoring database through SQLAlchemy.

A repository instead of a raw driver in tests: SQL lives in one place and
parameters are bound by name (`:user_id`) instead of being interpolated into an
f-string — that is both injection safety and correct type escaping. Every query
is logged with its parameters, so a failing DB check can be reproduced by hand
straight from the log.

SQLAlchemy is imported lazily: without the package (or the DB driver) installed
the suite still collects, and tests marked `db` are simply skipped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import allure

from utils.logger import get_logger


if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.engine import Connection

log = get_logger("db")

# Returned when the user has no stored transaction yet.
NO_DECISION = ""

LAST_DECISION_SQL = """
    SELECT decision FROM transactions
     WHERE user_id = :user_id
     ORDER BY created_at DESC
     LIMIT 1
"""
COUNT_FOR_USER_SQL = "SELECT count(*) FROM transactions WHERE user_id = :user_id"


def build_engine(url: str) -> Engine:
    """Engine for the scoring database: one per run, connections come from its pool.

    `pool_pre_ping` costs one cheap round trip per checkout and saves the suite
    from stale connections when a stand is redeployed mid-run. Pool sizing is
    left at the SQLAlchemy default — a test suite holds one connection at a time.
    """
    from sqlalchemy import create_engine  # noqa: PLC0415 — lazy import, see module docstring

    engine = create_engine(url, pool_pre_ping=True)

    log.info("database engine ready: %s", engine.url.render_as_string(hide_password=True))
    return engine


class TransactionsRepository:
    """Read-only repository over the transactions table."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    @allure.step("Read decision of the last transaction from DB")
    def last_decision(self, user_id: str) -> str:
        """Decision of the user's last transaction, blank when there is none."""
        row = self._fetch_one(LAST_DECISION_SQL, {"user_id": user_id})
        decision = str(row[0]) if row and row[0] else NO_DECISION

        log.info("DB decision for user %s: %r", user_id, decision)
        return decision

    @allure.step("Count transactions of a user in DB")
    def count_for_user(self, user_id: str) -> int:
        row = self._fetch_one(COUNT_FOR_USER_SQL, {"user_id": user_id})
        count = int(row[0]) if row else 0

        log.info("DB holds %s transaction(s) for user %s", count, user_id)
        return count

    def _fetch_one(self, statement: str, params: dict[str, Any]) -> tuple[Any, ...]:
        """First row of a query, or an empty tuple when nothing matched."""
        from sqlalchemy import text  # noqa: PLC0415 — lazy import, see module docstring

        log.debug("SQL: %s | params: %s", " ".join(statement.split()), params)

        result = self._connection.execute(text(statement), params)
        row = result.first()
        values = tuple(row) if row else ()

        log.debug("SQL row: %s", values)
        return values
