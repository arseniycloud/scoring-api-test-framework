"""Database transport: engine, pool and the two cursors.

Everything here is about *how* a query reaches the database, never *which*
query it is — the same split as `base_client.py` for HTTP. Domain queries live
in `scoring_db_client.py`.

Nothing is held between queries. The client owns the engine, and every query
takes a cursor from the pool inside a `with` block: leaving the block closes
the transaction (committing it for writes) and hands the connection back. A
test never leaves an "idle in transaction" session behind on the stand, and one
test cannot block another on the same rows.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, text

from utils.logger import get_logger


if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import Connection, Engine

log = get_logger("db")


def build_engine(url: str) -> Engine:
    """Engine for a database: one per run, connections come from its pool.

    `pool_pre_ping` costs one cheap round trip per checkout and saves the suite
    from stale connections when a stand is redeployed mid-run. Pool sizing is
    left at the SQLAlchemy default — a test suite holds one connection at a time.
    """
    engine = create_engine(url, pool_pre_ping=True)

    log.info("database engine ready: %s", engine.url.render_as_string(hide_password=True))
    return engine


class BaseDbClient:
    """Transport: hands out cursors and runs a statement, knows no SQL of its own."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def cursor(self) -> Iterator[Connection]:
        """A read cursor for one operation, returned to the pool when the block ends.

        Named queries cover what the tests need; this is the escape hatch for a
        one-off check, and it keeps the same no-holds guarantee:

            with scoring_db.cursor() as cur:
                cur.execute(text("SELECT ..."), {"user_id": user_id})
        """
        with self.engine.connect() as connection:
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

        with self.engine.begin() as connection:
            yield connection

        log.debug("write transaction committed")

    def fetch_one(self, statement: str, params: dict[str, Any]) -> tuple[Any, ...]:
        """First row of a query, or an empty tuple when nothing matched."""
        log.debug("SQL: %s | params: %s", " ".join(statement.split()), params)

        with self.cursor() as connection:
            row = connection.execute(text(statement), params).first()

        values = tuple(row) if row else ()
        log.debug("SQL row: %s", values)
        return values
