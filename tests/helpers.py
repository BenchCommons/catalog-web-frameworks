"""Shared test helpers: import path, fixtures and a stub HTTP server."""

from __future__ import annotations

import contextlib
import email.utils
import io
import itertools
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
FIXTURES = TESTS / "fixtures"
sys.path.insert(0, str(REPO / "tools"))

import catalog  # noqa: E402,F401
import verify  # noqa: E402,F401

_clock = itertools.count(1_700_000_000)


def fresh_date() -> str:
    """A different, valid IMF-fixdate on every call (no sleeping needed)."""
    return email.utils.formatdate(next(_clock), usegmt=True)


def response(body=b"", status=200, content_type="application/json", **overrides):
    """Build a stub response. Header overrides: pass None to omit a header."""
    if isinstance(body, str):
        body = body.encode()
    headers = {
        "Server": "stub",
        "Date": fresh_date,
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
    }
    for name, value in overrides.items():
        headers[name.replace("_", "-")] = value
    return status, headers, body


class StubServer:
    """Local HTTP server; ``routes`` maps path -> callable returning response()."""

    def __init__(self, routes):
        self.routes = routes
        stub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):  # noqa: N802
                route = stub.routes.get(self.path)
                if route is None:
                    status, headers, body = response(b"not found", 404, "text/plain")
                else:
                    status, headers, body = route()
                self.send_response_only(status)
                for name, value in headers.items():
                    if value is None:
                        continue
                    self.send_header(name, value() if callable(value) else value)
                if headers.get("Content-Length") is None and headers.get("Transfer-Encoding") is None:
                    self.send_header("Connection", "close")
                    self.close_connection = True
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


@contextlib.contextmanager
def captured():
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def run_cli(*argv):
    with captured() as (out, err):
        code = catalog.main(list(argv))
    return code, out.getvalue(), err.getvalue()
