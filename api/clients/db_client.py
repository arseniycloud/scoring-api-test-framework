"""Access to the scoring database through SQLAlchemy.

A repository instead of a raw driver in tests: SQL lives in one place and
parameters are bound by name (`:user_id`) instead of being interpolated into an
f-string — that is both injection safety and correct type escaping. Every query
is logged with its parameters, so a failing DB check can be reproduced by hand
straight from the log.

Nothing is held between queries. `ScoringDatabase` owns the engine, and every
query takes a cursor from the pool inside a `with` block: leaving the block
closes the transaction (committing it for writes) and hands the connection
back. A test never leaves an "idle in transaction" session behind on the
stand, and one test cannot block another on the same rows.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import allure
from sqlalchemy import create_engine, text

from utils.logger import get_logger


if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import Connection, Engine

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
    engine = create_engine(url, pool_pre_ping=True)

    log.info("database engine ready: %s", engine.url.render_as_string(hide_password=True))
    return engine


@contextmanager
def scoring_database(url: str) -> Iterator[ScoringDatabase]:
    """Database for the whole run; the engine and its pool are disposed on exit."""
    engine = build_engine(url)
    try:
        yield ScoringDatabase(engine)
    finally:
        engine.dispose()
        log.info("database engine disposed")


class ScoringDatabase:
    """Access to the scoring database: named queries, no SQL in tests."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager
    def cursor(self) -> Iterator[Connection]:
        """A read cursor for one operation, returned to the pool when the block ends.

        Named queries below cover what the tests need; this is the escape hatch
        for a one-off check, and it keeps the same no-holds guarantee:

            with scoring_db.cursor() as cur:
                cur.execute(text("SELECT ..."), {"user_id": user_id})
        """
        with self._engine.connect() as connection:
            yield connection

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """A write cursor: commits when the block ends, rolls back on any exception.

        For state the API cannot produce — seeding a row, clearing what a test
        left behind. Commit and rollback are the block's job, so a failing test
        never leaves half-written data:

            with scoring_db.transaction() as cur:
                cur.execute(text("DELETE FROM transactions WHERE user_id = :user_id"), params)
        """
        log.debug("opening a write transaction")

        with self._engine.begin() as connection:
            yield connection

        log.debug("write transaction committed")

    @allure.step("Read decision of the last transaction from DB")
    def last_decision(self, user_id: str) -> str:
        """Decision of the user's last transaction, blank when there is none."""
        row = self._fetch_one(LAST_DECISION_SQL, {"user_id": user_id})
        decision = str(row[0]) if row and row[0] else NO_DECISION

        log.info("DB decision for user %s: %r", user_id, decision)
        return decision

    @allure.step("Count transactions of a user in DB")
    def count_transactions(self, user_id: str) -> int:
        """How many transactions the database holds for a user."""
        row = self._fetch_one(COUNT_FOR_USER_SQL, {"user_id": user_id})
        count = int(row[0]) if row else 0

        log.info("DB holds %s transaction(s) for user %s", count, user_id)
        return count

    def _fetch_one(self, statement: str, params: dict[str, Any]) -> tuple[Any, ...]:
        """First row of a query, or an empty tuple when nothing matched."""
        log.debug("SQL: %s | params: %s", " ".join(statement.split()), params)

        with self.cursor() as connection:
            row = connection.execute(text(statement), params).first()

        values = tuple(row) if row else ()
        log.debug("SQL row: %s", values)
        return values
