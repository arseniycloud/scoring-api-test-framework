import allure
import pytest

from api.utils.constants import SCR_INVALID_DATA, SCR_RESPONSE_KEYS, Category, Country, Decision
from api.utils.db_validators import assert_db_decision
from api.utils.payloads import high_risk_transaction, transaction, transaction_body_invalid_amount
from api.utils.validators import assert_decision, assert_keys, assert_status_code, assert_valid_json
from utils.utils import HTTP_STATUS_BAD_REQUEST, HTTP_STATUS_NOT_FOUND, HTTP_STATUS_OK


@allure.epic("Scoring API")
@allure.feature("Transactions")
@allure.description("Tests for transaction creation, scoring decision and persistence.")
class TestTransactionScoring:
    @allure.title("Positive: POST transaction returns 200 and gets scored")
    @pytest.mark.positive
    @pytest.mark.smoke
    def test_post_transaction(self, scoring_client, test_data):
        payload = high_risk_transaction(test_data["user_id"])

        response = scoring_client.create_transaction(payload)
        assert_status_code(response, HTTP_STATUS_OK)

        scored = scoring_client.wait_for_scored(test_data["user_id"])
        assert_decision(scored, Decision.BLOCK)

    @allure.title("Positive: GET transactions returns 200 with list")
    @pytest.mark.positive
    def test_get_transactions(self, scoring_client, test_data):
        scoring_client.create_transaction(high_risk_transaction(test_data["user_id"]))

        response = scoring_client.get_transactions_response(test_data["user_id"])
        assert_status_code(response, HTTP_STATUS_OK)

        data = assert_valid_json(response)
        assert isinstance(data, list)
        assert len(data) > 0

    @allure.title("Positive: GET transactions response structure")
    @pytest.mark.positive
    def test_get_transactions_response_structure(self, scoring_client, test_data):
        scoring_client.create_transaction(high_risk_transaction(test_data["user_id"]))
        scoring_client.wait_for_scored(test_data["user_id"])

        response = scoring_client.get_transactions_response(test_data["user_id"])
        assert_status_code(response, HTTP_STATUS_OK)

        data = assert_valid_json(response)
        for item in data[:3]:
            assert_keys(item, SCR_RESPONSE_KEYS["transaction"], "Transaction")

    @allure.title("Positive: high-risk transaction is blocked and stored in DB")
    @pytest.mark.positive
    @pytest.mark.db
    def test_high_risk_transaction_is_blocked(self, scoring_client, scoring_db, test_data):
        payload = high_risk_transaction(test_data["user_id"])

        response = scoring_client.create_transaction(payload)
        assert_status_code(response, HTTP_STATUS_OK)

        scored = scoring_client.wait_for_scored(test_data["user_id"])
        assert_decision(scored, Decision.BLOCK)
        assert_db_decision(scoring_db.last_decision(test_data["user_id"]), Decision.BLOCK)

    @allure.title("Positive: decision depends on amount, category and country")
    @pytest.mark.positive
    @pytest.mark.parametrize(
        ("amount", "category", "country", "expected"),
        [
            pytest.param(100, Category.GROCERY, Country.SA, Decision.APPROVE, id="small-local"),
            pytest.param(75_000, Category.CRYPTO, Country.AE, Decision.BLOCK, id="large-foreign"),
        ],
    )
    def test_decision_by_profile(self, scoring_client, test_data, amount, category, country, expected):
        payload = transaction(test_data["user_id"], amount, category, country)

        response = scoring_client.create_transaction(payload)
        assert_status_code(response, HTTP_STATUS_OK)

        scored = scoring_client.wait_for_scored(test_data["user_id"])
        assert_decision(scored, expected)

    @allure.title("Negative: POST transaction with invalid amount")
    @pytest.mark.negative
    def test_post_transaction_invalid_amount(self, scoring_client, test_data):
        body = transaction_body_invalid_amount(test_data["user_id"])

        response = scoring_client.create_transaction_raw(body)
        assert_status_code(response, HTTP_STATUS_BAD_REQUEST)

    @allure.title("Negative: POST transaction with unknown user")
    @pytest.mark.negative
    def test_post_transaction_unknown_user(self, scoring_client):
        payload = high_risk_transaction(SCR_INVALID_DATA["user_id"])

        response = scoring_client.create_transaction(payload)
        assert_status_code(response, HTTP_STATUS_NOT_FOUND)

    @allure.title("Negative: GET transactions of non-existent user")
    @pytest.mark.negative
    def test_get_transactions_unknown_user(self, scoring_client):
        response = scoring_client.get_transactions_response(SCR_INVALID_DATA["user_id"])
        assert_status_code(response, HTTP_STATUS_NOT_FOUND)
