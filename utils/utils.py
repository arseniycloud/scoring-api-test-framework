"""Shared helpers and constants that are not tied to a specific API.

HTTP statuses are kept here as one list: tests read `HTTP_STATUS_OK` instead
of a magic 200. Values come from `http.HTTPStatus`, so `.value` and `.phrase`
stay available for failure messages. Only the statuses this suite actually
uses are declared — an unused alias is a name to read, not a feature.
"""

import os
from http import HTTPStatus


HTTP_STATUS_OK = HTTPStatus.OK
HTTP_STATUS_CREATED = HTTPStatus.CREATED
HTTP_STATUS_NO_CONTENT = HTTPStatus.NO_CONTENT
HTTP_STATUS_BAD_REQUEST = HTTPStatus.BAD_REQUEST
HTTP_STATUS_NOT_FOUND = HTTPStatus.NOT_FOUND

RETRYABLE_STATUSES = (
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.INTERNAL_SERVER_ERROR,
    HTTPStatus.BAD_GATEWAY,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
)

BODY_PREVIEW_LIMIT = 500


def env_str(name: str, default: str = "") -> str:
    """String from the environment with a default."""
    return os.environ.get(name, default)


def env_float(name: str, default: float) -> float:
    """Number from the environment: empty means default, garbage means a clear error."""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        message = f"Environment variable {name}={raw!r} must be a number"
        raise ValueError(message) from exc


def env_int(name: str, default: int) -> int:
    """Integer from the environment."""
    return int(env_float(name, default))
