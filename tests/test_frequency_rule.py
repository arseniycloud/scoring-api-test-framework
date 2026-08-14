import allure
import pytest

from api.utils.constants import SCR_LIMITS, Decision
from api.utils.db_validators import assert_db_count
from api.utils.payloads import grocery_transaction
from api.utils.validators import assert_decision, assert_status_code
from utils.utils import HTTP_STATUS_OK


FREQUENCY_THRESHOLD = SCR_LIMITS["frequency_threshold"]


@allure.epic("Scoring API")
@allure.feature("Frequency rule")
@allure.description("Tests for the rule that sends a user to manual review after N payments in a row.")
class TestFrequencyRule:
    @allure.title("Positive: transactions under the threshold are approved")
    @pytest.mark.positive
    @pytest.mark.parametrize("transactions_count", [1, 3], ids=["single", "under-limit"])
    def test_frequency_rule_under_threshold(self, scoring_client, test_data, transactions_count):
        payload = grocery_transaction(test_data["user_id"])

        for _ in range(transactions_count):
            assert_status_code(scoring_client.create_transaction(payload), HTTP_STATUS_OK)

        scored = scoring_client.wait_for_scored(test_data["user_id"])
        assert_decision(scored, Decision.APPROVE)

    @allure.title("Positive: transactions over the threshold go to manual review")
    @pytest.mark.positive
    @pytest.mark.smoke
    def test_frequency_rule_over_threshold(self, scoring_client, test_data):
        payload = grocery_transaction(test_data["user_id"])

        for _ in range(FREQUENCY_THRESHOLD + 1):
            assert_status_code(scoring_client.create_transaction(payload), HTTP_STATUS_OK)

        scored = scoring_client.wait_for_scored(test_data["user_id"])
        assert_decision(scored, Decision.MANUAL_REVIEW)

    @allure.title("Positive: every sent transaction is persisted in API and DB")
    @pytest.mark.positive
    @pytest.mark.db
    def test_all_transactions_are_persisted(self, scoring_client, scoring_db, test_data):
        payload = grocery_transaction(test_data["user_id"])
        expected_count = FREQUENCY_THRESHOLD + 1

        for _ in range(expected_count):
            assert_status_code(scoring_client.create_transaction(payload), HTTP_STATUS_OK)
        scoring_client.wait_for_scored(test_data["user_id"])

        transactions = scoring_client.get_transactions(test_data["user_id"])
        assert len(transactions) == expected_count
        assert_db_count(scoring_db.count_transactions(test_data["user_id"]), expected_count)
