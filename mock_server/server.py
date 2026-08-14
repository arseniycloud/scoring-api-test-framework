"""How a request reaches a handler.

Generic plumbing: it knows nothing about scoring, only how to match a request
against `ROUTES` and write back whatever the handler returned. All three HTTP
methods go through one dispatch, so there are no per-method if-chains.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from mock_server.scoring import ROUTES, Request


HOST = "127.0.0.1"
PORT = 8099


class MockScoringHandler(BaseHTTPRequestHandler):
    """Matches a request against ROUTES and returns the handler's answer."""

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def log_message(self, *args: Any) -> None:
        """Silence the default stderr access log; the framework logs the calls."""

    def _dispatch(self, method: str) -> None:
        url = urlparse(self.path)

        for route_method, pattern, handler in ROUTES:
            match = pattern.match(url.path)
            if route_method == method and match:
                request = Request(match.groups(), self._read_body(), self._read_query(url.query))
                self._send(*handler(request))
                return

        self._send(404, {"error": "not found"})

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    @staticmethod
    def _read_query(query: str) -> dict[str, str]:
        return {key: values[0] for key, values in parse_qs(query).items()}

    def _send(self, status: int, payload: Any = None) -> None:
        body = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(status)

        if body:
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))

        self.end_headers()
        self.wfile.write(body)


def run(host: str = HOST, port: int = PORT) -> None:
    """Serve until interrupted."""
    HTTPServer((host, port), MockScoringHandler).serve_forever()
