"""In-memory stub of the Scoring API.

Not a mock library and not part of the framework — a throwaway service so the
suite can be run by anyone who clones the repo, and so the tests are proven to
be able to fail. Standard library only, no extra dependencies.

    python3 stub/scoring_stub.py &
    SCORING_BASE_URL=http://127.0.0.1:8099 pytest -m "not db"
"""

import json
import re
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


USERS = {}
TRANSACTIONS = {}
COUNTRIES = {"SA", "AE"}
USER_RE = re.compile(r"^/api/users/([^/]+)$")


def decide(user_id, txn):
    count = len(TRANSACTIONS[user_id])
    if count > 5:
        return "MANUAL_REVIEW"
    if txn["amount"] >= 50_000 or (
        txn["category"] == "crypto" and txn["country"] != USERS[user_id]["country"]
    ):
        return "BLOCK"
    return "APPROVE"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, payload=None):
        body = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(code)
        if body:
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._body()

        if path == "/api/users":
            if not body.get("name") or body.get("country") not in COUNTRIES:
                return self._send(400, {"error": "invalid user payload"})
            user_id = str(uuid.uuid4())
            USERS[user_id] = {"id": user_id, "name": body["name"], "country": body["country"]}
            TRANSACTIONS[user_id] = []
            return self._send(201, USERS[user_id])

        if path == "/api/transactions":
            user_id = body.get("user_id")
            if not isinstance(body.get("amount"), int):
                return self._send(400, {"error": "invalid amount"})
            if user_id not in USERS:
                return self._send(404, {"error": "user not found"})
            txn = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "amount": body["amount"],
                "currency": body.get("currency", "SAR"),
                "category": body.get("category", "grocery"),
                "country": body.get("country", "SA"),
                "decision": None,
                "created_at": datetime.now(UTC).isoformat(),
            }
            TRANSACTIONS[user_id].append(txn)
            txn["decision"] = decide(user_id, txn)
            return self._send(200, txn)

        return self._send(404, {"error": "not found"})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/transactions":
            user_id = parse_qs(parsed.query).get("user_id", [""])[0]
            if user_id not in USERS:
                return self._send(404, {"error": "user not found"})
            return self._send(200, TRANSACTIONS[user_id])

        match = USER_RE.match(parsed.path)
        if match:
            user = USERS.get(match.group(1))
            return self._send(200, user) if user else self._send(404, {"error": "user not found"})

        return self._send(404, {"error": "not found"})

    def do_DELETE(self):
        match = USER_RE.match(urlparse(self.path).path)
        if match and match.group(1) in USERS:
            USERS.pop(match.group(1))
            TRANSACTIONS.pop(match.group(1), None)
            return self._send(204)
        return self._send(404, {"error": "user not found"})


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8099), Handler).serve_forever()
