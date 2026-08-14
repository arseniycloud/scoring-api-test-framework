"""Logging helpers.

Every module logs through `get_logger(...)`, so the whole framework writes
under one `scoring.*` tree: one line in `pytest.ini` changes verbosity for all
of it, and CI can grep by module (`scoring.http`, `scoring.db`, `scoring.check`).

Anything that may carry a credential goes through `mask_secrets` first — a
database URL or an auth header must never reach CI output.
"""

from __future__ import annotations

import logging
import re

from utils.utils import BODY_PREVIEW_LIMIT


MASK = "***"

# postgresql+psycopg2://user:password@host/db -> postgresql+psycopg2://user:***@host/db
_URL_PASSWORD = re.compile(r"(://[^:@\s]+:)[^@\s]+")

# password=hunter2 | "token": "abc" | Authorization: Bearer xyz -> key stays, value hidden
_SECRET_VALUE = re.compile(
    r"(?i)(password|token|secret|api[_-]?key|authorization)"  # key name
    r"(['\"]?\s*[=:]\s*)"  # separator: = or :, quotes optional
    r"[^,;\n]+"  # the value, up to the next field
)


def get_logger(name: str) -> logging.Logger:
    """Logger for a framework module: `get_logger("http")` -> `scoring.http`."""
    return logging.getLogger(f"scoring.{name}")


def mask_secrets(text: str) -> str:
    """Replace credential values with `***`, keeping the key readable."""
    text = _URL_PASSWORD.sub(rf"\1{MASK}", text)
    return _SECRET_VALUE.sub(rf"\1\2{MASK}", text)


def preview(text: str, limit: int = BODY_PREVIEW_LIMIT) -> str:
    """Shorten a payload for a log line and hide credentials in it."""
    if not text:
        return "<empty>"

    masked = mask_secrets(text)
    if len(masked) <= limit:
        return masked
    return f"{masked[:limit]}… ({len(masked)} chars total)"


def silence_noisy_loggers(level: int = logging.WARNING) -> None:
    """Keep third-party DEBUG chatter (urllib3, asyncio) out of the run log."""
    for name in ("urllib3", "asyncio"):
        logging.getLogger(name).setLevel(level)
