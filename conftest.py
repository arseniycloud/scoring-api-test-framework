"""Pytest entry point.

Fixtures live in `fixtures/`, split by what they serve:

    fixtures/environment.py — run configuration and CLI options
    fixtures/clients.py     — the API client and the database repository
    fixtures/data.py        — test data and its cleanup

They are registered as plugins here, so this file stays a table of contents
and a test only ever sees fixture names.
"""

pytest_plugins = [
    "fixtures.environment",
    "fixtures.clients",
    "fixtures.data",
]
