import json
import unittest

from helpers import FIXTURES, catalog, run_cli


class LoadCatalogTest(unittest.TestCase):
    def setUp(self):
        self.frameworks = catalog.load_catalog(FIXTURES / "valid")
        self.variants = {v.id: v for v in catalog.all_variants(self.frameworks)}

    def test_discovers_frameworks_and_variants(self):
        self.assertEqual([fw.id for fw in self.frameworks], ["Go/hello", "Python/dbonly"])
        self.assertEqual(
            sorted(self.variants),
            ["Go/hello:alt", "Go/hello:custom", "Go/hello:default", "Go/hello:old",
             "Python/dbonly:default"],
        )

    def test_dockerfile_resolution(self):
        self.assertEqual(self.variants["Go/hello:default"].dockerfile, "hello.dockerfile")
        self.assertEqual(self.variants["Go/hello:alt"].dockerfile, "hello-alt.dockerfile")
        self.assertEqual(self.variants["Go/hello:custom"].dockerfile, "custom.dockerfile")

    def test_port_string_is_accepted(self):
        self.assertEqual(self.variants["Go/hello:alt"].port, 8081)

    def test_database_normalized(self):
        dbs = {k: v.database for k, v in self.variants.items()}
        self.assertEqual(dbs["Go/hello:default"], "postgres")
        self.assertEqual(dbs["Go/hello:alt"], "mysql")
        self.assertEqual(dbs["Go/hello:custom"], "none")
        self.assertEqual(dbs["Go/hello:old"], "mongodb")

    def test_broken_tag(self):
        self.assertTrue(self.variants["Go/hello:old"].broken)
        self.assertFalse(self.variants["Go/hello:default"].broken)

    def test_stage_a_types(self):
        self.assertEqual(self.variants["Go/hello:default"].stage_types("A"), ["json", "plaintext"])
        self.assertEqual(self.variants["Python/dbonly:default"].stage_types("A"), [])


class CheckCommandTest(unittest.TestCase):
    def test_valid_catalog_passes_with_counts(self):
        code, out, _ = run_cli("--root", str(FIXTURES / "valid"), "check", "--json")
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(report["languages"], 2)
        self.assertEqual(report["frameworks"], 2)
        self.assertEqual(report["variants"], 5)
        self.assertEqual(report["broken"], 1)
        self.assertEqual(report["test_types"]["json"], {"stage": "A", "declared": 3, "non_broken": 2})
        self.assertEqual(report["test_types"]["db"]["declared"], 2)
        self.assertEqual(report["errors"], [])

    def test_text_report(self):
        code, out, _ = run_cli("--root", str(FIXTURES / "valid"), "check")
        self.assertEqual(code, 0)
        self.assertIn("frameworks: 2  variants: 5  broken: 1", out)
        self.assertIn("stage B [declared, not verified]", out)

    def test_missing_dockerfile_fails(self):
        code, out, _ = run_cli("--root", str(FIXTURES / "missing-dockerfile"), "check")
        self.assertEqual(code, 1)
        self.assertIn("Go/nodf:default: Dockerfile not found: nodf.dockerfile", out)

    def test_no_urls_fails(self):
        code, out, _ = run_cli("--root", str(FIXTURES / "no-urls"), "check")
        self.assertEqual(code, 1)
        self.assertIn("Go/nourls:default: no known *_url declared", out)

    def test_bad_json_fails(self):
        code, out, _ = run_cli("--root", str(FIXTURES / "bad-json"), "check")
        self.assertEqual(code, 1)
        self.assertIn("Go/broken-json: benchmark_config.json does not parse", out)


class ListCommandTest(unittest.TestCase):
    def test_list_text(self):
        code, out, _ = run_cli("--root", str(FIXTURES / "valid"), "list", "--lang", "go")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("Go/hello:default\tjson,plaintext", lines)
        self.assertIn("Go/hello:old\tjson\tbroken", lines)
        self.assertFalse(any(line.startswith("Python/") for line in lines))

    def test_list_json(self):
        code, out, _ = run_cli("--root", str(FIXTURES / "valid"), "list", "--json")
        self.assertEqual(code, 0)
        rows = {r["id"]: r for r in json.loads(out)}
        self.assertEqual(rows["Python/dbonly:default"]["stage_a"], [])
        self.assertEqual(rows["Python/dbonly:default"]["test_types"], ["db", "fortune"])
        self.assertTrue(rows["Go/hello:old"]["broken"])


if __name__ == "__main__":
    unittest.main()
