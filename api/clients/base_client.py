"""Base HTTP client.

Timeouts, retries, logging and Allure attachments live here — everything that
does not depend on a specific endpoint. Tests never touch `requests` directly,
so every call the suite makes is logged in one place and in one format.
"""

from __future__ import annotations

import json
from typing import Any

import allure
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.config import Config
from utils.logger import get_logger, mask_secrets, preview
from utils.utils import RETRYABLE_STATUSES


log = get_logger("http")


def build_session(config: Config) -> requests.Session:
    """Session with retries on connection errors, 429 and 5xx."""
    retry = Retry(
        total=config.total_retries,
        backoff_factor=config.backoff_factor,
        status_forcelist=RETRYABLE_STATUSES,
        raise_on_status=False,
        allowed_methods=frozenset({"GET", "POST", "DELETE"}),
    )
    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"Accept": "application/json"})

    log.info("HTTP session ready: base_url=%s timeout=%ss", config.base_url, config.request_timeout)
    log.debug("retries=%s backoff=%ss", config.total_retries, config.backoff_factor)
    return session


class BaseApiClient:
    """Transport: builds URLs, applies timeouts, logs and reports every call."""

    def __init__(self, config: Config, session: requests.Session) -> None:
        self.config = config
        self.session = session

    def url(self, path: str) -> str:
        """Absolute URL from an endpoint path."""
        return f"{self.config.base_url}{path}"

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.config.request_timeout)
        url = self.url(path)

        with allure.step(f"{method} {url}"):
            self._log_request(method, url, kwargs)
            response = self.session.request(method, url, **kwargs)
            self._log_response(response)
            self._attach(response)
            return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    # --- logging and reporting ------------------------------------------ #

    @staticmethod
    def _log_request(method: str, url: str, kwargs: dict[str, Any]) -> None:
        log.info("--> %s %s", method, url)

        params = kwargs.get("params")
        if params:
            log.debug("    params: %s", mask_secrets(str(params)))

        body = kwargs.get("json")
        if body is not None:
            log.debug("    body: %s", preview(json.dumps(body, ensure_ascii=False, default=str)))

    @staticmethod
    def _log_response(response: requests.Response) -> None:
        elapsed_ms = response.elapsed.total_seconds() * 1000
        log.info("<-- %s %s (%.0f ms)", response.status_code, response.reason or "", elapsed_ms)
        log.debug("    body: %s", preview(response.text))

    @staticmethod
    def _attach(response: requests.Response) -> None:
        """Put the response into Allure so a failure is debuggable without a rerun."""
        body = f"{response.status_code}\n{preview(response.text)}"
        allure.attach(body, name="response", attachment_type=allure.attachment_type.TEXT)
