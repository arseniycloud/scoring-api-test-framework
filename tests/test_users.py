import allure
import pytest

from api.utils.constants import SCR_INVALID_DATA, SCR_RESPONSE_KEYS
from api.utils.payloads import new_user, user_body_invalid_country, user_body_without_name
from api.utils.validators import assert_created, assert_keys, assert_status_code
from utils.utils import HTTP_STATUS_BAD_REQUEST, HTTP_STATUS_NO_CONTENT, HTTP_STATUS_NOT_FOUND


@allure.epic("Scoring API")
@allure.feature("Users")
@allure.description("Tests for user creation, response structure and deletion.")
class TestUsers:
    @allure.title("Positive: POST user returns 201 with id")
    @pytest.mark.positive
    @pytest.mark.smoke
    def test_post_user(self, scoring_client, created_users):
        response = scoring_client.create_user(new_user("Smoke User"))

        data = assert_created(response)
        created_users.append(data["id"])

    @allure.title("Positive: POST user response structure")
    @pytest.mark.positive
    def test_post_user_response_structure(self, scoring_client, created_users):
        response = scoring_client.create_user(new_user("Structure User"))

        data = assert_created(response)
        created_users.append(data["id"])
        assert_keys(data, SCR_RESPONSE_KEYS["user"], "User")

    @allure.title("Positive: DELETE user returns 204")
    @pytest.mark.positive
    def test_delete_user(self, scoring_client):
        data = assert_created(scoring_client.create_user(new_user("Deleted User")))

        response = scoring_client.delete_user(data["id"])
        assert_status_code(response, HTTP_STATUS_NO_CONTENT)

    @allure.title("Negative: POST user with invalid country")
    @pytest.mark.negative
    def test_post_user_invalid_country(self, scoring_client):
        response = scoring_client.create_user_raw(user_body_invalid_country())
        assert_status_code(response, HTTP_STATUS_BAD_REQUEST)

    @allure.title("Negative: POST user without required name")
    @pytest.mark.negative
    def test_post_user_without_name(self, scoring_client):
        response = scoring_client.create_user_raw(user_body_without_name())
        assert_status_code(response, HTTP_STATUS_BAD_REQUEST)

    @allure.title("Negative: GET non-existent user")
    @pytest.mark.negative
    def test_get_unknown_user(self, scoring_client):
        response = scoring_client.get_user(SCR_INVALID_DATA["user_id"])
        assert_status_code(response, HTTP_STATUS_NOT_FOUND)

    @allure.title("Negative: DELETE non-existent user")
    @pytest.mark.negative
    def test_delete_unknown_user(self, scoring_client):
        response = scoring_client.delete_user(SCR_INVALID_DATA["user_id"])
        assert_status_code(response, HTTP_STATUS_NOT_FOUND)
