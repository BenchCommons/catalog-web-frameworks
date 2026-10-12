"""`catalog.py verify` orchestration with a fake Docker and a stub server."""

import json
import re
import tempfile
import unittest
from pathlib import Path

from helpers import FIXTURES, StubServer, captured, catalog, response, verify


class FakeDocker:
    def __init__(self, base_url, build_results=None, running=True):
        self.base_url_value = base_url
        self.build_results = list(build_results or [])
        self.is_running = running
        self.calls = []

    def build(self, context, dockerfile, tag, build_args):
        self.calls.append(("build", dockerfile, tag, build_args["TFB_TEST_NAME"]))
        ok = self.build_results.pop(0) if self.build_results else True
        return ok, "" if ok else "network error"

    def network_create(self, name):
        self.calls.append(("network_create", name))

    def network_remove(self, name):
        self.calls.append(("network_remove", name))

    def run(self, image, name, network, port):
        self.calls.append(("run", image, port))
        return name

    def base_url(self, name, port):
        return self.base_url_value

    def running(self, name):
        return self.is_running

    def logs(self, name, tail=50):
        return "app log line"

    def remove(self, name):
        self.calls.append(("remove", name))

    def remove_image(self, tag):
        self.calls.append(("rmi", tag))

    def names(self, kind):
        return [c for c in self.calls if c[0] == kind]


ROUTES = {
    "/json": lambda: response('{"message":"Hello, World!"}'),
    "/plaintext": lambda: response("Hello, World!", content_type="text/plain"),
}


class VerifyCommandTest(unittest.TestCase):
    def run_verify(self, docker, *targets, extra=()):
        argv = ["--root", str(FIXTURES / "valid"), "verify", *targets, "--date-delay", "0",
                "--port-timeout", "2", *extra]
        args = catalog.parser().parse_args(argv)
        with captured() as (out, _err):
            code = catalog.cmd_verify(args, docker=docker)
        return code, out.getvalue()

    def test_framework_target_verifies_non_broken_variants(self):
        with StubServer(ROUTES) as srv:
            docker = FakeDocker(srv.url)
            with tempfile.TemporaryDirectory() as tmp:
                summary = Path(tmp) / "s.json"
                code, out = self.run_verify(docker, "Go/hello", extra=("--summary", str(summary)))
                data = json.loads(summary.read_text())
        self.assertEqual(code, 0, out)
        self.assertIn("Go/hello:default json pass", out)
        self.assertIn("Go/hello:default plaintext pass", out)
        self.assertIn("Go/hello:default db declared-not-verified", out)
        self.assertIn("Go/hello:old json skipped-broken", out)
        built = [c[1] for c in docker.names("build")]
        self.assertEqual(built, ["hello.dockerfile", "hello-alt.dockerfile", "custom.dockerfile"])
        self.assertEqual([c[3] for c in docker.names("build")], ["hello", "hello-alt", "hello-custom"])
        self.assertEqual(docker.names("run")[1][2], 8081)
        # Every started container and network is cleaned up.
        self.assertEqual(len(docker.names("remove")), 3)
        self.assertEqual(len(docker.names("network_remove")), 3)
        statuses = {v["id"]: {t: r["status"] for t, r in v["test_types"].items()}
                    for v in data["variants"]}
        self.assertEqual(statuses["Go/hello:old"], {"json": "skipped-broken"})
        self.assertEqual(data["stage"], "A")

    def test_variant_target_and_db_only_variant_is_not_built(self):
        docker = FakeDocker("http://127.0.0.1:9")
        code, out = self.run_verify(docker, "Python/dbonly:default")
        self.assertEqual(code, 0)
        self.assertEqual(docker.names("build"), [])
        self.assertIn("Python/dbonly:default db declared-not-verified", out)
        self.assertIn("Python/dbonly:default fortune declared-not-verified", out)

    def test_build_failure_is_retried_once(self):
        with StubServer(ROUTES) as srv:
            docker = FakeDocker(srv.url, build_results=[False, True])
            code, out = self.run_verify(docker, "Go/hello:alt")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(docker.names("build")), 2)
        self.assertIn("retried", out)

    def test_build_failure_twice_fails_stage_a_types(self):
        docker = FakeDocker("http://127.0.0.1:9", build_results=[False, False])
        code, out = self.run_verify(docker, "Go/hello:default")
        self.assertEqual(code, 1)
        self.assertIn("Go/hello:default json fail", out)
        self.assertIn("Go/hello:default db declared-not-verified", out)
        self.assertEqual(docker.names("run"), [])

    def test_container_exit_fails_and_cleans_up(self):
        docker = FakeDocker("http://127.0.0.1:9", running=False)
        code, out = self.run_verify(docker, "Go/hello:alt", extra=("--rmi",))
        self.assertEqual(code, 1)
        self.assertIn("container exited", out)
        self.assertIn("app log line", out)
        self.assertEqual(len(docker.names("remove")), 1)
        self.assertEqual(len(docker.names("network_remove")), 1)
        self.assertEqual(len(docker.names("rmi")), 1)

    def test_port_timeout_fails(self):
        docker = FakeDocker("http://127.0.0.1:9")
        code, out = self.run_verify(docker, "Go/hello:alt")
        self.assertEqual(code, 1)
        self.assertIn("no HTTP response on port 8081", out)

    def test_failing_response_fails(self):
        routes = dict(ROUTES, **{"/json": lambda: response('{"message":"nope"}')})
        with StubServer(routes) as srv:
            code, out = self.run_verify(FakeDocker(srv.url), "Go/hello:default")
        self.assertEqual(code, 1)
        self.assertIn("Go/hello:default json fail", out)
        self.assertIn("Go/hello:default plaintext pass", out)

    def test_unknown_target_fails(self):
        code, _ = self.run_verify(FakeDocker("http://127.0.0.1:9"), "Go/nope")
        self.assertEqual(code, 1)


class ImageTagTest(unittest.TestCase):
    def test_tags_are_valid_docker_references(self):
        ref = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*$")
        for v in catalog.all_variants(catalog.load_catalog(FIXTURES / "valid")):
            v.language, v.folder = "C++", "Hello_World.NET"
            tag = catalog.image_tag(v)
            self.assertRegex(tag, ref)


class SummarizeTest(unittest.TestCase):
    def test_merges_shards(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b, out = Path(tmp) / "a.json", Path(tmp) / "b.json", Path(tmp) / "all.json"
            a.write_text(json.dumps({"variants": [
                {"id": "Go/x:default", "test_types": {"json": {"status": "pass", "findings": []}}}]}))
            b.write_text(json.dumps({"variants": [
                {"id": "C/y:default", "test_types": {
                    "json": {"status": "fail", "findings": []},
                    "db": {"status": verify.NOT_VERIFIED, "findings": []}}}]}))
            with captured() as (stdout, _):
                catalog.main(["summarize", str(a), str(b), "--out", str(out)])
            merged = json.loads(out.read_text())
        self.assertEqual([v["id"] for v in merged["variants"]], ["C/y:default", "Go/x:default"])
        self.assertEqual(merged["counts"], {"fail": 1, "declared-not-verified": 1, "pass": 1})
        self.assertIn("| C/y:default | json | fail |", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
