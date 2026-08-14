"""Mock server for the Scoring API.

A fake service, not a mock library: it answers the same endpoints the framework
calls, so anyone who clones the repo can run the suite, and so the tests are
proven able to fail. Standard library only, no extra dependencies.

    python3 -m mock_server &
    SCORING_BASE_URL=http://127.0.0.1:8099 pytest -m "not db"

    scoring.py — what the fake service does: state, rules, endpoint handlers
    server.py  — how a request reaches a handler: one routing table, no if-chains
"""

from mock_server.server import run


__all__ = ["run"]
