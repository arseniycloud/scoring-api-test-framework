"""Pydantic models for Scoring API requests and responses.

A payload is built by a model, not by a raw dict: a typo in a key or a wrong
type fails while building the request instead of turning into an obscure 400
from the service.

Response models declare only the fields the framework actually reads. The rest
of the body is kept as-is (`extra="allow"`) and still shows up in `as_dict()`,
so nothing is lost in logs and failure messages. Missing fields fall back to an
empty value instead of `None`: there is one "no value" state, not two.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.utils.constants import Category, Country, Currency


# The service leaves the decision empty until the transaction is scored.
NOT_SCORED = ""


class ApiModel(BaseModel):
    """Base for everything that crosses the wire."""

    model_config = ConfigDict(extra="allow")

    def as_dict(self) -> dict[str, Any]:
        """Model as a plain dict: a request body, or an object for a log line."""
        return self.model_dump(mode="json")


class UserPayload(ApiModel):
    """Request body for user creation."""

    name: str = Field(min_length=1)
    country: Country = Country.SA


class TransactionPayload(ApiModel):
    """Request body for transaction creation."""

    user_id: str
    amount: int = Field(gt=0)
    currency: Currency = Currency.SAR
    category: Category = Category.GROCERY
    country: Country = Country.SA


class User(ApiModel):
    """User object returned by the service."""

    id: str = ""


class Transaction(ApiModel):
    """Transaction object returned by the service."""

    id: str = ""
    decision: str = NOT_SCORED

    @field_validator("decision", mode="before")
    @classmethod
    def _blank_when_not_scored(cls, value: Any) -> str:
        """The service sends null until scoring finishes — read that as blank."""
        return value or NOT_SCORED
