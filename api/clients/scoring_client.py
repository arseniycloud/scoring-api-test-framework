"""Scoring API client — the only place where domain requests are built."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import allure
import requests

from api.clients.base_client import BaseApiClient, build_session
from api.models import NOT_SCORED, Transaction, TransactionPayload, User, UserPayload
from api.utils.validators import assert_created, assert_status_code, assert_valid_json
from utils.config import Config
from utils.logger import get_logger
from utils.utils import HTTP_STATUS_OK


log = get_logger("scoring")

USERS = "/api/users"
TRANSACTIONS = "/api/transactions"


@contextmanager
def scoring_api(config: Config) -> Iterator[ScoringClient]:
    """Client for the whole run; the HTTP session is closed on exit."""
    session = build_session(config)
    try:
        yield ScoringClient(config, session)
    finally:
        session.close()
        log.info("HTTP session closed")


class ScoringClient(BaseApiClient):
    """Domain methods on top of the transport layer.

    The client does not check business rules — that is the tests' job. It only
    guarantees a response is parseable and returns typed models. Methods with
    the `_raw` suffix take an arbitrary body: they exist for negative tests,
    where an invalid payload cannot be built from a model.
    """

    # --- users --------------------------------------------------------- #

    def create_user(self, payload: UserPayload) -> requests.Response:
        return self.post(USERS, json=payload.as_dict())

    def create_user_raw(self, body: dict[str, Any]) -> requests.Response:
        return self.post(USERS, json=body)

    def get_user(self, user_id: str) -> requests.Response:
        return self.get(f"{USERS}/{user_id}")

    def delete_user(self, user_id: str) -> requests.Response:
        return self.delete(f"{USERS}/{user_id}")

    @allure.step("Create user and read its id")
    def create_user_and_get_id(self, payload: UserPayload) -> str:
        data = assert_created(self.create_user(payload))
        user_id = User.model_validate(data).id

        log.info("user created: id=%s name=%s", user_id, payload.name)
        return user_id

    # --- transactions -------------------------------------------------- #

    def create_transaction(self, payload: TransactionPayload) -> requests.Response:
        log.info(
            "sending transaction: user=%s amount=%s %s category=%s country=%s",
            payload.user_id,
            payload.amount,
            payload.currency,
            payload.category,
            payload.country,
        )
        return self.post(TRANSACTIONS, json=payload.as_dict())

    def create_transaction_raw(self, body: dict[str, Any]) -> requests.Response:
        return self.post(TRANSACTIONS, json=body)

    def get_transactions_response(self, user_id: str, **params: str | int) -> requests.Response:
        return self.get(TRANSACTIONS, params={"user_id": user_id, **params})

    @allure.step("Get transactions of a user")
    def get_transactions(self, user_id: str, **params: str | int) -> list[Transaction]:
        response = self.get_transactions_response(user_id, **params)
        assert_status_code(response, HTTP_STATUS_OK)

        data = assert_valid_json(response)
        transactions = [Transaction.model_validate(item) for item in data]

        log.debug("user %s has %s transaction(s)", user_id, len(transactions))
        return transactions

    # --- waiting for an async decision ---------------------------------- #

    @allure.step("Wait until the last transaction is scored")
    def wait_for_scored(self, user_id: str) -> Transaction:
        """Wait until the user's last transaction leaves the unscored state.

        Scoring is asynchronous, so instead of `time.sleep()` in a test we poll
        with a deadline: a fast service does not make the test wait, a slow one
        does not make it flaky. Timeout and interval come from the config.

        The client waits, the test asserts. It deliberately does not take the
        expected decision: a wrong decision must fail on the test's own
        `assert_decision`, not disappear into a timeout here.
        """
        limit = self.config.decision_timeout
        started = time.monotonic()
        deadline = started + limit
        attempt = 0
        last_seen: dict[str, Any] = {}

        log.info("waiting up to %ss for a decision (user=%s)", limit, user_id)

        while True:
            attempt += 1
            transactions = self.get_transactions(user_id)

            if transactions:
                last = transactions[-1]
                last_seen = last.as_dict()

                if last.decision != NOT_SCORED:
                    waited = time.monotonic() - started
                    log.info("scored %s after %.1fs (%s poll(s))", last.decision, waited, attempt)
                    return last

            log.debug("poll %s: not scored yet, last seen %s", attempt, last_seen)

            if time.monotonic() >= deadline:
                message = (
                    f"No scoring decision within {limit}s for user_id={user_id}. "
                    f"Last transaction: {last_seen}"
                )

                log.error(message)
                raise AssertionError(message)

            time.sleep(self.config.decision_poll_interval)
