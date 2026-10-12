"""Correctness verifiers for the web frameworks catalog (spec 001, R5).

Callers use one function, :func:`verify_variant`. It takes the base URL of a
running implementation and the variant's ``*_url`` routes, runs the verifiers
for the requested stage and returns one result per declared test type.

Stage A (json, plaintext) is implemented here. Test types of later stages are
reported as ``declared-not-verified``.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from .client import Response, fetch as http_fetch
from .rules import Finding, verify_json, verify_plaintext

# url key in benchmark_config.json -> (test type, stage)
TEST_TYPES = {
    "json_url": ("json", "A"),
    "plaintext_url": ("plaintext", "A"),
    "db_url": ("db", "B"),
    "query_url": ("query", "B"),
    "fortune_url": ("fortune", "B"),
    "update_url": ("update", "B"),
    "cached_query_url": ("cached-query", "C"),
}
STAGES = ("A", "B", "C")
IMPLEMENTED_STAGES = ("A",)

PASS = "pass"
WARN = "warn"
FAIL = "fail"
NOT_VERIFIED = "declared-not-verified"
SKIPPED_BROKEN = "skipped-broken"

_VERIFIERS = {
    "json": verify_json,
    "plaintext": verify_plaintext,
}

Fetch = Callable[[str, str], Response]


def stage_of(test_type: str) -> str:
    for name, stage in TEST_TYPES.values():
        if name == test_type:
            return stage
    raise KeyError(test_type)


def declared_types(urls: Dict[str, str]) -> Dict[str, str]:
    """Map test type -> route for every known ``*_url`` key present."""
    out = {}
    for key, (name, _stage) in TEST_TYPES.items():
        if urls.get(key):
            out[name] = urls[key]
    return out


def types_for_stage(urls: Dict[str, str], stage: str = "A") -> Dict[str, str]:
    """Declared test types verified at ``stage`` (stages are cumulative)."""
    limit = STAGES.index(stage)
    return {
        name: route
        for name, route in declared_types(urls).items()
        if STAGES.index(stage_of(name)) <= limit
    }


def summarize(findings) -> str:
    levels = {f.level for f in findings}
    if FAIL in levels:
        return FAIL
    if WARN in levels:
        return WARN
    return PASS


def verify_variant(
    base_url: str,
    urls: Dict[str, str],
    stage: str = "A",
    fetch: Optional[Fetch] = None,
    date_delay: float = 3.0,
) -> Dict[str, dict]:
    """Verify one running variant.

    ``urls`` maps ``*_url`` keys to routes, as in ``benchmark_config.json``.
    Returns ``{test_type: {"status": ..., "findings": [...]}}`` for every
    declared test type, in ``TEST_TYPES`` order.
    """
    if stage not in IMPLEMENTED_STAGES:
        raise ValueError("stage %s is not implemented yet" % stage)
    fetch = fetch or http_fetch
    base_url = base_url.rstrip("/")
    wanted = types_for_stage(urls, stage)
    results: Dict[str, dict] = {}
    for name, route in declared_types(urls).items():
        if name not in wanted:
            results[name] = {"status": NOT_VERIFIED, "findings": []}
            continue
        findings = _VERIFIERS[name](base_url, route, fetch, date_delay)
        results[name] = {
            "status": summarize(findings),
            "findings": [f.as_dict() for f in findings],
        }
    return results


__all__ = [
    "Finding",
    "Response",
    "TEST_TYPES",
    "STAGES",
    "PASS",
    "WARN",
    "FAIL",
    "NOT_VERIFIED",
    "SKIPPED_BROKEN",
    "declared_types",
    "types_for_stage",
    "verify_variant",
]
