"""Stage A rules: common response checks, json and plaintext (spec 001, R5).

Clean-room implementation of the documented behaviour of the TFB verifier at
the pinned upstream commit. Each check yields findings at level ``pass``,
``warn`` or ``fail``; a test type fails if any finding fails.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Callable, List

from .client import Response

# Minimum route lengths: "/json" and "/plaintext".
MIN_ROUTE = {"json": 5, "plaintext": 10}

CONTENT_TYPES = {
    "json": re.compile(r"^application/json(; ?charset=(UTF|utf)-8)?$"),
    "plaintext": re.compile(r"^text/plain(; ?charset=(UTF|utf)-8)?$"),
    "html": re.compile(r"^text/html; ?charset=(UTF|utf)-8$"),
}

# IMF-fixdate (RFC 7231 section 7.1.1.1). "UTC" is accepted like upstream.
DATE_RE = re.compile(
    r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{2} "
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4} "
    r"\d{2}:\d{2}:\d{2} (GMT|UTC)$"
)

HELLO = "hello, world!"


@dataclass
class Finding:
    level: str  # "warn" or "fail"
    message: str
    url: str

    def as_dict(self) -> dict:
        return {"level": self.level, "message": self.message, "url": self.url}


Fetch = Callable[[str, str], Response]


def _fail(msg, url):
    return Finding("fail", msg, url)


def _warn(msg, url):
    return Finding("warn", msg, url)


def check_body_present(resp: Response, url: str) -> List[Finding]:
    if resp.status is None:
        return [_fail("No response (%s)" % (resp.error or "unknown error"), url)]
    if not resp.body:
        return [_fail("Empty response body", url)]
    return []


def check_route(test_type: str, route: str, url: str) -> List[Finding]:
    minimum = MIN_ROUTE[test_type]
    if len(route) < minimum:
        return [
            _fail(
                "Route for %s must be at least %d characters, found '%s'"
                % (test_type, minimum, route),
                url,
            )
        ]
    return []


def check_status(resp: Response, url: str, expected: int = 200) -> List[Finding]:
    if resp.status != expected:
        return [_fail("HTTP status %s, expected %d" % (resp.status, expected), url)]
    return []


def check_headers(
    resp: Response,
    url: str,
    content_type: str,
    refetch: Callable[[], Response],
    date_delay: float,
) -> List[Finding]:
    """Required headers, Date format, Date not cached, Content-Type."""
    out: List[Finding] = []
    for name in ("Server", "Date", "Content-Type"):
        if resp.header(name) is None:
            out.append(_fail("Required response header missing: %s" % name, url))
    if resp.header("Content-Length") is None and resp.header("Transfer-Encoding") is None:
        out.append(
            _fail(
                "Required size header missing: include Content-Length or Transfer-Encoding",
                url,
            )
        )

    date = resp.header("Date")
    if date is not None and not DATE_RE.match(date):
        out.append(_warn("Date header '%s' is not an RFC 7231 IMF-fixdate" % date, url))

    if date_delay:
        time.sleep(date_delay)
    second = refetch()
    if date is not None and second.header("Date") == date:
        out.append(
            _fail(
                "Date header is cached: '%s' on two requests %gs apart" % (date, date_delay),
                url,
            )
        )

    ctype = resp.header("Content-Type")
    if ctype is not None and not CONTENT_TYPES[content_type].match(ctype):
        out.append(
            _fail(
                "Content-Type '%s' does not match '%s'"
                % (ctype, CONTENT_TYPES[content_type].pattern),
                url,
            )
        )
    return out


def check_hello_object(obj, url: str) -> List[Finding]:
    if not isinstance(obj, dict) or not all(isinstance(v, str) for v in obj.values()):
        return [_fail("Body is not a JSON object of string values", url)]
    lowered = {k.lower(): v.lower() for k, v in obj.items()}
    if "message" not in lowered:
        return [_fail("Missing required key 'message'", url)]
    if lowered["message"] != HELLO:
        return [_fail("Expected message 'Hello, World!', got '%s'" % obj_message(obj), url)]
    extra = [k for k in obj if k.lower() != "message"]
    if extra:
        return [_warn("Extra JSON keys, consider removing: %s" % ", ".join(extra), url)]
    return []


def obj_message(obj) -> str:
    for k, v in obj.items():
        if k.lower() == "message":
            return v
    return ""


def verify_json(base_url: str, route: str, fetch: Fetch, date_delay: float = 3.0) -> List[Finding]:
    url = base_url + route
    resp = fetch(url, "json")
    problems = check_body_present(resp, url)
    parsed = None
    if not problems:
        try:
            parsed = json.loads(resp.body)
        except ValueError as exc:
            problems.append(_fail("Invalid JSON: %s" % exc, url))
    problems += check_route("json", route, url)
    if problems:
        return problems
    problems += check_hello_object(parsed, url)
    problems += check_status(resp, url)
    problems += check_headers(resp, url, "json", lambda: fetch(url, "json"), date_delay)
    return problems


def verify_plaintext(
    base_url: str, route: str, fetch: Fetch, date_delay: float = 3.0
) -> List[Finding]:
    url = base_url + route
    resp = fetch(url, "plaintext")
    problems = check_body_present(resp, url) + check_route("plaintext", route, url)
    if problems:
        return problems
    body = resp.body.lower()
    expected = HELLO.encode()
    if expected not in body:
        return [_fail("Body does not contain 'Hello, World!'", url)]
    extra = len(body) - len(expected)
    if extra > 0:
        problems.append(_warn("Body has %d byte(s) more than 'Hello, World!'" % extra, url))
    problems += check_status(resp, url)
    problems += check_headers(resp, url, "plaintext", lambda: fetch(url, "plaintext"), date_delay)
    return problems
