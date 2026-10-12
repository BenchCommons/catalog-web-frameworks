#!/usr/bin/env python3
"""Catalog tooling for BenchCommons/catalog-web-frameworks (spec 001, plan section 3).

Stdlib only, Python 3.9+. Commands:

  check                          metadata check over the whole catalog
  list [--lang L] [--json]       list variants
  changed --since REF [--json]   changed framework folders (ALL_TOOLING for tooling changes)
  lint-docker --since REF        reject :latest / untagged FROM in changed Dockerfiles
  verify TARGET [--stage A]      build, run and verify variants (TARGET: Lang, Lang/fw or Lang/fw:key)
  summarize FILE...              merge verify summaries into one JSON and a Markdown report

Every command takes --root to point at a catalog directory (default: repo root).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify as verifier  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_NAME = "benchmark_config.json"
NON_CATALOG_DIRS = {"tools", "tests", "docs"}
TOOLING_PREFIXES = ("tools/", "tests/", ".github/workflows/")
ALL_TOOLING = "ALL_TOOLING"
# Fixed smoke sample verified when tooling changes (plan section 4): one
# variant per major language that needs no database at startup, so stage A
# can pass on hosted CI without a dataset.
SMOKE_SAMPLE = (
    "C/libreactor:default",
    "Go/go-std:default",
    "Java/javalin:default",
    "JavaScript/express:default",
    "Python/fastpysgi:default",
    "Rust/axum:default",
)
DATABASES = {"postgres": "postgres", "postgresql": "postgres", "mysql": "mysql",
             "mongodb": "mongodb", "mongo": "mongodb", "none": "none"}
PORT_WAIT_SECONDS = 120


# --------------------------------------------------------------------------
# Catalog model


@dataclass
class Variant:
    language: str
    folder: str  # framework folder name
    key: str
    framework: str  # "framework" field of the config
    path: Path  # framework folder
    config: dict
    dockerfile: Optional[str] = None
    port: Optional[int] = None
    urls: Dict[str, str] = field(default_factory=dict)
    database: str = "none"
    broken: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return "%s/%s:%s" % (self.language, self.folder, self.key)

    @property
    def test_name(self) -> str:
        return self.framework if self.key == "default" else "%s-%s" % (self.framework, self.key)

    def stage_types(self, stage: str = "A") -> List[str]:
        return list(verifier.types_for_stage(self.urls, stage))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "language": self.language,
            "framework": self.folder,
            "key": self.key,
            "dockerfile": self.dockerfile,
            "port": self.port,
            "database": self.database,
            "broken": self.broken,
            "test_types": list(verifier.declared_types(self.urls)),
            "stage_a": self.stage_types("A"),
        }


@dataclass
class Framework:
    language: str
    name: str
    path: Path
    variants: List[Variant] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return "%s/%s" % (self.language, self.name)


def framework_dirs(root: Path) -> List[Path]:
    out = []
    for lang in sorted(p for p in root.iterdir() if p.is_dir()):
        if lang.name.startswith(".") or lang.name in NON_CATALOG_DIRS:
            continue
        for fw in sorted(p for p in lang.iterdir() if p.is_dir()):
            if (fw / CONFIG_NAME).is_file():
                out.append(fw)
    return out


def normalize_database(value) -> Optional[str]:
    if value is None:
        return "none"
    return DATABASES.get(str(value).strip().lower())


def load_framework(path: Path) -> Framework:
    fw = Framework(path.parent.name, path.name, path)
    try:
        with open(path / CONFIG_NAME, encoding="utf-8") as fh:
            config = json.load(fh)
    except (OSError, ValueError) as exc:
        fw.errors.append("%s does not parse: %s" % (CONFIG_NAME, exc))
        return fw
    if not isinstance(config, dict):
        fw.errors.append("%s is not a JSON object" % CONFIG_NAME)
        return fw
    name = config.get("framework")
    if not isinstance(name, str) or not name:
        fw.errors.append("missing 'framework' name")
        return fw
    tests = config.get("tests")
    if not isinstance(tests, list) or not tests or not all(isinstance(t, dict) for t in tests):
        fw.errors.append("'tests' must be a non-empty list of objects")
        return fw
    seen = set()
    for group in tests:
        for key, test in group.items():
            if key in seen:
                fw.errors.append("duplicate variant key '%s'" % key)
                continue
            seen.add(key)
            fw.variants.append(load_variant(fw, name, key, test))
    return fw


def load_variant(fw: Framework, name: str, key: str, test) -> Variant:
    v = Variant(fw.language, fw.name, key, name, fw.path, test if isinstance(test, dict) else {})
    if not isinstance(test, dict):
        v.errors.append("variant is not an object")
        return v
    tags = test.get("tags") or []
    v.broken = isinstance(tags, list) and "broken" in tags

    port = test.get("port")
    if isinstance(port, bool):
        port = None
    if isinstance(port, str) and port.strip().isdigit():
        port = int(port.strip())
    if isinstance(port, int) and 0 < port < 65536:
        v.port = port
    else:
        v.errors.append("missing or invalid port: %r" % (test.get("port"),))

    v.urls = {k: test[k] for k in verifier.TEST_TYPES if isinstance(test.get(k), str) and test[k]}
    if not v.urls:
        v.errors.append("no known *_url declared")

    dockerfile = test.get("dockerfile") or "%s.dockerfile" % v.test_name
    v.dockerfile = dockerfile
    if not (fw.path / dockerfile).is_file():
        v.errors.append("Dockerfile not found: %s" % dockerfile)

    db = normalize_database(test.get("database"))
    if db is None:
        v.warnings.append("unknown database %r" % test.get("database"))
        v.database = str(test.get("database"))
    else:
        v.database = db
    return v


def load_catalog(root: Path) -> List[Framework]:
    return [load_framework(p) for p in framework_dirs(root)]


def all_variants(frameworks: Iterable[Framework]) -> List[Variant]:
    return [v for fw in frameworks for v in fw.variants]


# --------------------------------------------------------------------------
# check / list


def cmd_check(args) -> int:
    root = Path(args.root)
    frameworks = load_catalog(root)
    variants = all_variants(frameworks)
    errors: List[str] = []
    warnings: List[str] = []
    for fw in frameworks:
        errors += ["%s: %s" % (fw.id, e) for e in fw.errors]
    for v in variants:
        errors += ["%s: %s" % (v.id, e) for e in v.errors]
        warnings += ["%s: %s" % (v.id, w) for w in v.warnings]

    languages = {fw.language for fw in frameworks}
    dockerfiles = sum(1 for fw in frameworks for _ in fw.path.glob("*.dockerfile"))
    by_type = Counter()
    by_type_ok = Counter()
    for v in variants:
        for name in verifier.declared_types(v.urls):
            by_type[name] += 1
            if not v.broken:
                by_type_ok[name] += 1
    databases = Counter(v.database for v in variants)
    broken = sum(1 for v in variants if v.broken)

    report = {
        "languages": len(languages),
        "frameworks": len(frameworks),
        "variants": len(variants),
        "broken": broken,
        "dockerfiles": dockerfiles,
        "databases": dict(databases.most_common()),
        "test_types": {
            name: {"stage": stage, "declared": by_type[name], "non_broken": by_type_ok[name]}
            for name, stage in verifier.TEST_TYPES.values()
        },
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("catalog: %s" % root.resolve())
        print("languages: %d  frameworks: %d  variants: %d  broken: %d  dockerfiles: %d"
              % (len(languages), len(frameworks), len(variants), broken, dockerfiles))
        print("databases: " + ", ".join("%s %d" % kv for kv in databases.most_common()))
        for stage in verifier.STAGES:
            parts = [
                "%s %d (%d non-broken)" % (name, by_type[name], by_type_ok[name])
                for name, s in verifier.TEST_TYPES.values() if s == stage
            ]
            label = "verified" if stage in verifier.IMPLEMENTED_STAGES else "declared, not verified"
            print("stage %s [%s]: %s" % (stage, label, ", ".join(parts)))
        for w in warnings:
            print("warning: " + w)
        for e in errors:
            print("error: " + e)
        print("%d error(s), %d warning(s)" % (len(errors), len(warnings)))
    return 1 if errors else 0


def cmd_list(args) -> int:
    variants = all_variants(load_catalog(Path(args.root)))
    if args.lang:
        variants = [v for v in variants if v.language.lower() == args.lang.lower()]
    if args.json:
        print(json.dumps([v.as_dict() for v in variants], indent=2))
        return 0
    for v in variants:
        types = ",".join(v.stage_types("A")) or "-"
        print("%s\t%s%s" % (v.id, types, "\tbroken" if v.broken else ""))
    return 0


# --------------------------------------------------------------------------
# git helpers: changed / lint-docker


def git(root: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", *argv], cwd=str(root), check=True, capture_output=True, text=True
    ).stdout


def changed_paths(root: Path, since: str, diff_filter: Optional[str] = None):
    """Return (toplevel, prefix, paths relative to the git toplevel)."""
    top = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    prefix = root.resolve().relative_to(top).as_posix()
    prefix = "" if prefix == "." else prefix + "/"
    argv = ["diff", "--name-only", "--no-renames"]
    if diff_filter:
        argv.append("--diff-filter=" + diff_filter)
    argv.append("%s...HEAD" % since)
    paths = [p for p in git(root, *argv).splitlines() if p]
    return top, prefix, paths


def changed_folders(root: Path, since: str):
    top, prefix, paths = changed_paths(root, since)
    tooling = any(p.startswith(TOOLING_PREFIXES) for p in paths)
    folders = []
    for p in paths:
        if not p.startswith(prefix):
            continue
        parts = p[len(prefix):].split("/")
        if len(parts) < 3 or parts[0].startswith(".") or parts[0] in NON_CATALOG_DIRS:
            continue
        folder = "%s/%s" % (parts[0], parts[1])
        if folder not in folders and (root / folder / CONFIG_NAME).is_file():
            folders.append(folder)
    return tooling, sorted(folders)


def cmd_changed(args) -> int:
    root = Path(args.root)
    tooling, folders = changed_folders(root, args.since)
    matrix = list(folders)
    if tooling:
        for f in SMOKE_SAMPLE:
            if f not in matrix and (root / f.split(":")[0] / CONFIG_NAME).is_file():
                matrix.append(f)
    if args.json:
        print(json.dumps({"tooling": tooling, "folders": folders, "matrix": matrix}))
        return 0
    if tooling:
        print(ALL_TOOLING)
    for f in folders:
        print(f)
    return 0


FROM_RE = re.compile(r"^\s*FROM\s+(.*)$", re.IGNORECASE)


def dockerfile_lines(text: str) -> List[tuple]:
    """Logical lines (line number, text): comments dropped, continuations joined."""
    out = []
    buf, start = "", 0
    for n, raw in enumerate(text.splitlines(), 1):
        if not buf and raw.lstrip().startswith("#"):
            continue
        if not buf:
            start = n
        line = raw.rstrip()
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        out.append((start, buf + line))
        buf = ""
    if buf:
        out.append((start, buf))
    return out


def lint_dockerfile(text: str) -> List[tuple]:
    """Return (line, message) for each FROM using :latest or no tag."""
    problems = []
    aliases = set()
    for n, line in dockerfile_lines(text):
        m = FROM_RE.match(line)
        if not m:
            continue
        tokens = [t for t in m.group(1).split() if not t.startswith("--")]
        if not tokens:
            problems.append((n, "FROM without an image"))
            continue
        image = tokens[0]
        if len(tokens) >= 3 and tokens[1].lower() == "as":
            aliases.add(tokens[2].lower())
        low = image.lower()
        if low == "scratch" or low in aliases or "$" in image or "@" in image:
            continue
        last = image.rsplit("/", 1)[-1]
        if ":" not in last:
            problems.append((n, "untagged base image '%s'" % image))
        elif last.split(":", 1)[1] == "latest":
            problems.append((n, "base image uses :latest '%s'" % image))
    return problems


def is_dockerfile(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.endswith(".dockerfile") or name == "Dockerfile"


def cmd_lint_docker(args) -> int:
    root = Path(args.root)
    if args.all:
        files = sorted(
            p for fw in framework_dirs(root) for p in fw.iterdir()
            if p.is_file() and is_dockerfile(p.name)
        )
    else:
        top, _prefix, paths = changed_paths(root, args.since, diff_filter="d")
        files = [top / p for p in paths if is_dockerfile(p)]
    bad = 0
    for path in files:
        for n, msg in lint_dockerfile(path.read_text(encoding="utf-8", errors="replace")):
            bad += 1
            print("%s:%d: %s" % (os.path.relpath(path, root), n, msg))
    print("lint-docker: %d Dockerfile(s) checked, %d problem(s)" % (len(files), bad))
    return 1 if bad else 0


# --------------------------------------------------------------------------
# verify


class Docker:
    """Thin wrapper over the docker CLI, replaceable in tests."""

    def __init__(self, platform: Optional[str] = None, build_timeout: int = 1800):
        self.platform = platform
        self.build_timeout = build_timeout

    def _run(self, argv, timeout=None, check=False):
        return subprocess.run(
            ["docker", *argv], capture_output=True, text=True, timeout=timeout, check=check
        )

    def build(self, context: Path, dockerfile: str, tag: str, build_args: Dict[str, str]):
        argv = ["build", "-f", str(context / dockerfile), "-t", tag]
        if self.platform:
            argv += ["--platform", self.platform]
        for k, v in build_args.items():
            argv += ["--build-arg", "%s=%s" % (k, v)]
        argv.append(str(context))
        try:
            proc = self._run(argv, timeout=self.build_timeout)
        except subprocess.TimeoutExpired:
            return False, "docker build timed out after %ds" % self.build_timeout
        return proc.returncode == 0, (proc.stdout + proc.stderr)[-4000:]

    def network_create(self, name: str):
        self._run(["network", "create", name], check=True)

    def network_remove(self, name: str):
        self._run(["network", "rm", name])

    def run(self, image: str, name: str, network: str, port: int):
        argv = ["run", "-d", "--name", name, "--network", network,
                "--network-alias", "tfb-server", "--init",
                "--ulimit", "nofile=65535:65535",
                "--sysctl", "net.core.somaxconn=65535",
                "-p", "127.0.0.1::%d" % port]
        if self.platform:
            argv += ["--platform", self.platform]
        argv.append(image)
        proc = self._run(argv)
        if proc.returncode != 0:
            raise RuntimeError("docker run failed: " + proc.stderr.strip())
        return name

    def base_url(self, name: str, port: int) -> Optional[str]:
        """Host URL of the published port, or None while it is not mapped."""
        proc = self._run(["port", name, "%d/tcp" % port])
        lines = proc.stdout.split()
        if proc.returncode != 0 or not lines:
            return None
        return "http://" + lines[0]

    def running(self, name: str) -> bool:
        proc = self._run(["inspect", "-f", "{{.State.Running}}", name])
        return proc.stdout.strip() == "true"

    def logs(self, name: str, tail: int = 50) -> str:
        proc = self._run(["logs", "--tail", str(tail), name])
        return proc.stdout + proc.stderr

    def remove(self, name: str):
        self._run(["rm", "-f", name])

    def remove_image(self, tag: str):
        self._run(["rmi", "-f", tag])


def wait_for_http(docker, name: str, port: int, route: str, timeout: float,
                  fetch=None):
    """Wait until the server answers HTTP on its published port.

    Returns (base_url, None) when ready, else (None, reason).
    """
    fetch = fetch or verifier.http_fetch
    deadline = time.monotonic() + timeout
    error = "port not published"
    while True:
        if not docker.running(name):
            return None, "container exited before serving HTTP"
        base_url = docker.base_url(name, port)
        if base_url:
            resp = fetch(base_url + route, "json")
            if resp.status is not None:
                return base_url, None
            error = resp.error
        if time.monotonic() >= deadline:
            return None, "no HTTP response on port %d after %ds (%s)" % (port, timeout, error)
        time.sleep(1)


def select_variants(frameworks: List[Framework], target: str) -> List[Variant]:
    target = target.strip().strip("/")
    key = None
    if ":" in target:
        target, key = target.split(":", 1)
    parts = target.split("/")
    out = []
    for fw in frameworks:
        if fw.language != parts[0] or (len(parts) > 1 and fw.name != parts[1]):
            continue
        out += [v for v in fw.variants if key is None or v.key == key]
    return out


def image_tag(v: Variant) -> str:
    name = ("%s-%s-%s" % (v.language, v.folder, v.key)).lower()
    return "cwf-verify/" + re.sub(r"[^a-z0-9_.-]+", "-", name).strip("-.")


def verify_one(v: Variant, docker, stage: str, args, fetch=None) -> dict:
    record = {"id": v.id, "language": v.language, "framework": v.folder, "key": v.key,
              "broken": v.broken, "test_types": {}, "notes": []}
    declared = verifier.declared_types(v.urls)
    if v.broken:
        record["test_types"] = {t: {"status": verifier.SKIPPED_BROKEN, "findings": []}
                                for t in declared}
        return record
    wanted = verifier.types_for_stage(v.urls, stage)
    if v.errors:
        record["notes"] += v.errors
        record["test_types"] = {t: {"status": verifier.FAIL if t in wanted else verifier.NOT_VERIFIED,
                                    "findings": []} for t in declared}
        return record
    if not wanted:
        record["test_types"] = {t: {"status": verifier.NOT_VERIFIED, "findings": []}
                                for t in declared}
        return record

    def fail_all(reason: str):
        record["notes"].append(reason)
        record["test_types"] = {
            t: {"status": verifier.FAIL if t in wanted else verifier.NOT_VERIFIED,
                "findings": [{"level": "fail", "message": reason, "url": ""}] if t in wanted else []}
            for t in declared}
        return record

    tag = image_tag(v)
    build_args = {"BENCHMARK_ENV": args.benchmark_env, "TFB_TEST_NAME": v.test_name,
                  "TFB_TEST_DATABASE": v.database}
    ok, log = docker.build(v.path, v.dockerfile, tag, build_args)
    if not ok:
        # One retry for transient (network) build failures, reported in the summary.
        record["notes"].append("docker build failed once; retried")
        ok, log = docker.build(v.path, v.dockerfile, tag, build_args)
    if not ok:
        record["build_log_tail"] = log[-2000:]
        return fail_all("docker build failed")

    suffix = uuid.uuid4().hex[:8]
    network, name = "cwf-verify-%s" % suffix, "cwf-%s" % suffix
    docker.network_create(network)
    try:
        try:
            docker.run(tag, name, network, v.port)
        except Exception as exc:  # noqa: BLE001
            return fail_all(str(exc))
        first_route = next(iter(wanted.values()))
        base_url, reason = wait_for_http(docker, name, v.port, first_route,
                                         args.port_timeout, fetch)
        if reason:
            record["container_log_tail"] = docker.logs(name)[-2000:]
            return fail_all(reason)
        record["test_types"] = verifier.verify_variant(
            base_url, v.urls, stage, fetch=fetch, date_delay=args.date_delay)
        if any(r["status"] == verifier.FAIL for r in record["test_types"].values()):
            record["container_log_tail"] = docker.logs(name)[-2000:]
        return record
    finally:
        docker.remove(name)
        docker.network_remove(network)
        if args.rmi:
            docker.remove_image(tag)


def print_record(record: dict, out=None):
    out = out or sys.stdout
    for name, res in record["test_types"].items():
        print("%s %s %s" % (record["id"], name, res["status"]), file=out)
        for f in res["findings"]:
            print("    %s: %s" % (f["level"], f["message"]), file=out)
    for note in record.get("notes", []):
        print("    note: %s" % note, file=out)
    for key in ("build_log_tail", "container_log_tail"):
        if record.get(key):
            print("    --- %s ---" % key, file=out)
            for line in record[key].splitlines()[-30:]:
                print("    | " + line, file=out)
    out.flush()


def record_failed(record: dict) -> bool:
    return any(r["status"] == verifier.FAIL for r in record["test_types"].values())


def cmd_verify(args, docker=None, fetch=None) -> int:
    root = Path(args.root)
    frameworks = load_catalog(root)
    docker = docker or Docker(platform=args.platform, build_timeout=args.build_timeout)
    records = []
    for target in args.targets:
        variants = select_variants(frameworks, target)
        if not variants:
            print("error: no variant matches '%s'" % target, file=sys.stderr)
            records.append({"id": target, "test_types": {}, "notes": ["no matching variant"],
                            "error": True})
            continue
        for v in variants:
            record = verify_one(v, docker, args.stage, args, fetch)
            print_record(record)
            records.append(record)
    if args.summary:
        Path(args.summary).write_text(json.dumps({"stage": args.stage, "variants": records},
                                                 indent=2) + "\n")
    failed = [r for r in records if r.get("error") or record_failed(r)]
    counts = status_counts(records)
    print("verify: %d variant(s); %s" % (len(records), format_counts(counts)))
    return 1 if failed else 0


def status_counts(records: Sequence[dict]) -> Counter:
    return Counter(r["status"] for rec in records for r in rec["test_types"].values())


def format_counts(counts: Counter) -> str:
    order = [verifier.PASS, verifier.WARN, verifier.FAIL, verifier.SKIPPED_BROKEN,
             verifier.NOT_VERIFIED]
    return ", ".join("%s %d" % (k, counts.get(k, 0)) for k in order)


def cmd_summarize(args) -> int:
    records = []
    for path in args.files:
        records += json.loads(Path(path).read_text()).get("variants", [])
    records.sort(key=lambda r: r["id"])
    counts = status_counts(records)
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"counts": dict(counts), "variants": records}, indent=2) + "\n")
    lines = ["## Catalog verification (stage A)", "",
             "%d variant(s): %s" % (len(records), format_counts(counts)), "",
             "| Variant | Test type | Status |", "|---|---|---|"]
    for rec in records:
        for name, res in rec["test_types"].items():
            if res["status"] in (verifier.FAIL, verifier.WARN):
                lines.append("| %s | %s | %s |" % (rec["id"], name, res["status"]))
    print("\n".join(lines))
    return 0


# --------------------------------------------------------------------------
# CLI


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="catalog.py", description=__doc__.split("\n")[0])
    p.add_argument("--root", default=str(REPO_ROOT),
                   help="catalog directory (default: repo root)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("check", help="metadata check over the whole catalog")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("list", help="list variants")
    s.add_argument("--lang")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("changed", help="changed framework folders since REF")
    s.add_argument("--since", required=True)
    s.add_argument("--json", action="store_true",
                   help="print {tooling, folders, matrix}; matrix adds the smoke sample")
    s.set_defaults(func=cmd_changed)

    s = sub.add_parser("lint-docker", help="reject :latest or untagged FROM images")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--since")
    g.add_argument("--all", action="store_true", help="lint every Dockerfile in the catalog")
    s.set_defaults(func=cmd_lint_docker)

    s = sub.add_parser("verify", help="build, run and verify variants")
    s.add_argument("targets", nargs="+", metavar="TARGET",
                   help="Language, Language/framework or Language/framework:key")
    s.add_argument("--stage", default="A", choices=list(verifier.IMPLEMENTED_STAGES))
    s.add_argument("--platform", help="docker --platform, e.g. linux/amd64")
    s.add_argument("--summary", help="write a JSON summary to this file")
    s.add_argument("--rmi", action="store_true", help="remove each image after verifying")
    s.add_argument("--build-timeout", type=int, default=1800)
    s.add_argument("--port-timeout", type=int, default=PORT_WAIT_SECONDS)
    s.add_argument("--date-delay", type=float, default=3.0, help=argparse.SUPPRESS)
    s.add_argument("--benchmark-env", default="ci", help=argparse.SUPPRESS)
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("summarize", help="merge verify summaries")
    s.add_argument("files", nargs="+")
    s.add_argument("--out", help="write the merged JSON here")
    s.set_defaults(func=cmd_summarize)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
