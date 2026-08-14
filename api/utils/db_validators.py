"""Custom validators for data stored in the scoring database.

`fail` is imported from `validators` rather than copied: both modules report a
failed check in exactly one way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import allure

from api.utils.validators import fail
from utils.logger import get_logger


if TYPE_CHECKING:
    from api.utils.constants import Decision

log = get_logger("check.db")


@allure.step("Assert decision stored in DB: {expected}")
def assert_db_decision(actual: str, expected: Decision) -> None:
    """Decision stored in the database equals the expected one."""
    if not actual:
        fail(f"No transaction with a decision in DB (expected {expected})")
    if actual != expected:
        fail(f"DB holds decision {actual}, expected {expected}")

    log.debug("DB decision %s as expected", expected)


@allure.step("Assert transaction count in DB: {expected}")
def assert_db_count(actual: int, expected: int) -> None:
    """Database holds exactly the expected number of transactions."""
    if actual != expected:
        fail(f"DB holds {actual} transaction(s), expected {expected}")

    log.debug("DB holds %s transaction(s) as expected", expected)
