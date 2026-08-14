"""Run configuration.

The only place that reads the environment: stand addresses, the database URL,
timeouts, retries and async-decision polling settings. `SCORING_DB_URL` is a
SQLAlchemy URL (`postgresql+psycopg2://user:pass@host:5432/scoring`).
Credentials never go to the repo — `.env` locally, secrets or Vault in CI.
"""

from __future__ import annotations

from dataclasses import dataclass

from utils.utils import env_float, env_int, env_str


DEFAULT_BASE_URL = "http://localhost:8080"


@dataclass(frozen=True)
class Config:
    """Immutable config: tests read it, they never change it."""

    base_url: str
    db_url: str

    request_timeout: float = 10.0
    total_retries: int = 3
    backoff_factor: float = 0.5

    decision_timeout: float = 15.0
    decision_poll_interval: float = 0.5

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            base_url=env_str("SCORING_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            db_url=env_str("SCORING_DB_URL"),
            request_timeout=env_float("SCORING_REQUEST_TIMEOUT", 10.0),
            total_retries=env_int("SCORING_RETRIES", 3),
            backoff_factor=env_float("SCORING_BACKOFF_FACTOR", 0.5),
            decision_timeout=env_float("SCORING_DECISION_TIMEOUT", 15.0),
            decision_poll_interval=env_float("SCORING_POLL_INTERVAL", 0.5),
        )

    @property
    def db_configured(self) -> bool:
        return bool(self.db_url)
