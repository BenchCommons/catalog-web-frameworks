"""Minimal HTTP GET used by the verifiers (stdlib only)."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, Optional

ACCEPT = {
    "json": "application/json,text/html;q=0.9,application/xhtml+xml;q=0.9,"
    "application/xml;q=0.8,*/*;q=0.7",
    "plaintext": "text/plain,text/html;q=0.9,application/xhtml+xml;q=0.9,"
    "application/xml;q=0.8,*/*;q=0.7",
}


@dataclass
class Response:
    status: Optional[int]
    headers: Dict[str, str] = field(default_factory=dict)  # lower-cased names
    body: Optional[bytes] = None
    error: Optional[str] = None

    def header(self, name: str) -> Optional[str]:
        return self.headers.get(name.lower())


def fetch(url: str, accept: str = "json", timeout: float = 15.0) -> Response:
    """GET ``url``. Never raises; transport errors go to ``Response.error``."""
    req = urllib.request.Request(url, headers={"Accept": ACCEPT.get(accept, accept)})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(resp.status, _headers(resp.headers), resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        return Response(exc.code, _headers(exc.headers), body)
    except Exception as exc:  # connection refused, reset, timeout, bad status line
        return Response(None, {}, None, "%s: %s" % (type(exc).__name__, exc))


def _headers(msg) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if msg is None:
        return out
    for name, value in msg.items():
        key = name.lower()
        out[key] = value if key not in out else out[key] + ", " + value
    return out
