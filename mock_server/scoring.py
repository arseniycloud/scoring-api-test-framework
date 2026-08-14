"""What the mock service does: its state, its scoring rules, its endpoints.

Every endpoint is a function taking a `Request` and returning `(status, body)`.
They are listed in `ROUTES` at the bottom — that table is the whole API surface,
readable in one screen.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


KNOWN_COUNTRIES = ("SA", "AE")
FREQUENCY_THRESHOLD = 5
HIGH_RISK_AMOUNT = 50_000

NOT_FOUND = "user not found"


@dataclass(frozen=True)
class Request:
    """What a handler gets: path parameters, parsed body, query parameters."""

    path_params: tuple[str, ...] = ()
    body: dict[str, Any] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)

    @property
    def user_id(self) -> str:
        """First path parameter for `/api/users/<id>`, or `?user_id=` for lists."""
        return self.path_params[0] if self.path_params else self.query.get("user_id", "")


# The whole state of the fake service.
USERS: dict[str, dict[str, Any]] = {}
TRANSACTIONS: dict[str, list[dict[str, Any]]] = {}


def decide(user_id: str, transaction: dict[str, Any]) -> str:
    """The two scoring rules the tests exercise."""
    if len(TRANSACTIONS[user_id]) > FREQUENCY_THRESHOLD:
        return "MANUAL_REVIEW"

    foreign_crypto = (
        transaction["category"] == "crypto" and transaction["country"] != USERS[user_id]["country"]
    )
    if transaction["amount"] >= HIGH_RISK_AMOUNT or foreign_crypto:
        return "BLOCK"

    return "APPROVE"


# --- endpoints ---------------------------------------------------------- #


def create_user(request: Request) -> tuple[int, Any]:
    body = request.body
    if not body.get("name") or body.get("country") not in KNOWN_COUNTRIES:
        return 400, {"error": "invalid user payload"}

    user_id = str(uuid.uuid4())
    USERS[user_id] = {"id": user_id, "name": body["name"], "country": body["country"]}
    TRANSACTIONS[user_id] = []
    return 201, USERS[user_id]


def get_user(request: Request) -> tuple[int, Any]:
    user = USERS.get(request.user_id)
    return (200, user) if user else (404, {"error": NOT_FOUND})


def delete_user(request: Request) -> tuple[int, Any]:
    if request.user_id not in USERS:
        return 404, {"error": NOT_FOUND}

    USERS.pop(request.user_id)
    TRANSACTIONS.pop(request.user_id, None)
    return 204, None


def create_transaction(request: Request) -> tuple[int, Any]:
    body = request.body
    if not isinstance(body.get("amount"), int):
        return 400, {"error": "invalid amount"}

    user_id = body.get("user_id", "")
    if user_id not in USERS:
        return 404, {"error": NOT_FOUND}

    transaction = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "amount": body["amount"],
        "currency": body.get("currency", "SAR"),
        "category": body.get("category", "grocery"),
        "country": body.get("country", "SA"),
        "decision": None,
        "created_at": datetime.now(UTC).isoformat(),
    }
    TRANSACTIONS[user_id].append(transaction)
    transaction["decision"] = decide(user_id, transaction)
    return 200, transaction


def list_transactions(request: Request) -> tuple[int, Any]:
    if request.user_id not in USERS:
        return 404, {"error": NOT_FOUND}

    return 200, TRANSACTIONS[request.user_id]


# method, path pattern, handler — the whole API in one table.
ROUTES = (
    ("POST", re.compile(r"^/api/users$"), create_user),
    ("GET", re.compile(r"^/api/users/([^/]+)$"), get_user),
    ("DELETE", re.compile(r"^/api/users/([^/]+)$"), delete_user),
    ("POST", re.compile(r"^/api/transactions$"), create_transaction),
    ("GET", re.compile(r"^/api/transactions$"), list_transactions),
)
