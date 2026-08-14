"""Test data factories.

Request bodies are built here, not in tests: a test says *what* it checks, the
factory says *which* data triggers the rule. Valid bodies come from Pydantic
models; `*_body` factories return raw dicts for negative cases, where an
invalid payload cannot be built from a model at all.
"""

from __future__ import annotations

from typing import Any

from api.models import TransactionPayload, UserPayload
from api.utils.constants import SCR_INVALID_DATA, SCR_LIMITS, Category, Country


DEFAULT_USER_NAME = "Test User"


def new_user(name: str = DEFAULT_USER_NAME, country: Country = Country.SA) -> UserPayload:
    """Valid user payload."""
    return UserPayload(name=name, country=country)


def high_risk_transaction(user_id: str) -> TransactionPayload:
    """Large foreign crypto payment — expected to be blocked."""
    return transaction(user_id, SCR_LIMITS["high_risk_amount"], Category.CRYPTO, Country.AE)


def grocery_transaction(user_id: str) -> TransactionPayload:
    """Small local grocery payment — expected to be approved."""
    return transaction(user_id, SCR_LIMITS["default_amount"], Category.GROCERY, Country.SA)


def transaction(user_id: str, amount: int, category: Category, country: Country) -> TransactionPayload:
    """Transaction payload with an explicit risk profile."""
    return TransactionPayload(user_id=user_id, amount=amount, category=category, country=country)


def user_body_invalid_country() -> dict[str, Any]:
    """User body with a country the service does not know."""
    return {"name": "Invalid User", "country": SCR_INVALID_DATA["country"]}


def user_body_without_name() -> dict[str, Any]:
    """User body missing the required name."""
    return {"country": Country.SA}


def transaction_body_invalid_amount(user_id: str) -> dict[str, Any]:
    """Transaction body where amount is a string instead of a number."""
    body = grocery_transaction(user_id).as_dict()
    body["amount"] = SCR_INVALID_DATA["amount"]
    return body
