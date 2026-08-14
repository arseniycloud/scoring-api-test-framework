"""Custom validators for HTTP responses and scoring decisions.

Checks live here, not in tests: a test reads as a scenario, and a failure
message is equally informative everywhere (method, URL, response body preview).
Every check also logs its outcome, so the log alone tells which assertion broke
and on which response. Database checks live in `db_validators.py`.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

import allure
import requests

from api.models import Transaction
from api.utils.constants import Decision
from utils.logger import get_logger, preview
from utils.utils import HTTP_STATUS_CREATED


log = get_logger("check")


def _describe(response: requests.Response) -> str:
    method = response.request.method if response.request is not None else "?"
    return f"{method} {response.url}"


def fail(message: str) -> None:
    """Log a failed check and raise it as a test failure.

    Shared with `db_validators` so both modules fail in exactly one way.
    """
    log.error(message)
    raise AssertionError(message)


# --- HTTP responses ---------------------------------------------------- #


@allure.step("Assert status code: {expected}")
def assert_status_code(response: requests.Response, expected: HTTPStatus) -> None:
    """Response status equals the expected one."""
    if response.status_code == expected:
        log.debug("status %s as expected: %s", expected.value, _describe(response))
        return

    fail(
        f"{_describe(response)}: expected {expected.value} ({expected.phrase}), "
        f"got {response.status_code}. Body: {preview(response.text)}"
    )


@allure.step("Assert response body is valid JSON")
def assert_valid_json(response: requests.Response) -> Any:
    """Response body parses as JSON; returns the parsed data."""
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        message = f"{_describe(response)}: body is not valid JSON ({exc}): {preview(response.text)}"
        log.exception(message)
        raise AssertionError(message) from exc


@allure.step("Assert resource is created")
def assert_created(response: requests.Response) -> dict[str, Any]:
    """Resource is created: 201 plus an id in the body. Returns the body."""
    assert_status_code(response, HTTP_STATUS_CREATED)

    data = assert_valid_json(response)
    if not data.get("id"):
        fail(f"{_describe(response)}: created resource has no id: {data}")
    return data


@allure.step("Assert object structure: {object_name}")
def assert_keys(payload: dict[str, Any], keys: list[str], object_name: str) -> None:
    """Response object contains every documented key."""
    missing = [key for key in keys if key not in payload]
    if missing:
        fail(f"{object_name} object missing keys {missing}: {payload}")

    log.debug("%s object has all documented keys: %s", object_name, keys)


@allure.step("Assert scoring decision: {expected}")
def assert_decision(transaction: Transaction, expected: Decision) -> None:
    """Scoring decision on a transaction equals the expected one."""
    if transaction.decision == expected:
        log.debug("decision %s as expected for transaction %s", expected, transaction.id)
        return

    fail(f"Expected {expected}, got {transaction.decision}: {transaction.as_dict()}")
