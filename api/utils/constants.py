"""Scoring API constants: response keys, invalid data, limits.

Endpoint paths live next to the client that calls them, in
`api/clients/scoring_client.py` — one owner, no indirection.
"""

from enum import StrEnum


SCR_RESPONSE_KEYS = {
    "user": ["id", "name", "country"],
    "transaction": ["id", "user_id", "amount", "currency", "category", "country", "decision"],
}

SCR_INVALID_DATA = {
    "user_id": "00000000-0000-0000-0000-000000000000",
    "amount": "not-a-number",
    "country": "ZZ",
}

# frequency_threshold — which consecutive payment sends the user to manual review.
SCR_LIMITS = {"frequency_threshold": 5, "high_risk_amount": 75_000, "default_amount": 100}


class Decision(StrEnum):
    """Scoring decision on a transaction."""

    APPROVE = "APPROVE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCK = "BLOCK"


class Currency(StrEnum):
    SAR = "SAR"
    AED = "AED"
    USD = "USD"


class Country(StrEnum):
    SA = "SA"
    AE = "AE"


class Category(StrEnum):
    CRYPTO = "crypto"
    GROCERY = "grocery"
    TRANSFER = "transfer"
