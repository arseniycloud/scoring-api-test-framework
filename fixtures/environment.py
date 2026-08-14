"""Run configuration: CLI options and logging setup.

Plumbing, not test material. A test never asks for `config` directly — it asks
for a client, and the client already carries this configuration.
"""

from __future__ import annotations

import pytest

from utils.config import Config
from utils.logger import get_logger, mask_secrets, silence_noisy_loggers


log = get_logger("fixture")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--scoring-base-url",
        action="store",
        default="",
        help="Base URL of the scoring service (overrides SCORING_BASE_URL)",
    )


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001 — pytest hook signature
    """Runs before collection: keep third-party DEBUG noise out of our log."""
    silence_noisy_loggers()


@pytest.fixture(scope="session")
def config(request: pytest.FixtureRequest) -> Config:
    """Run configuration: environment variables, overridden by CLI options."""
    run_config = Config.from_env(base_url=request.config.getoption("--scoring-base-url"))

    log.info("run config: base_url=%s db_configured=%s", run_config.base_url, run_config.db_configured)
    log.debug("full config: %s", mask_secrets(str(run_config)))
    return run_config
