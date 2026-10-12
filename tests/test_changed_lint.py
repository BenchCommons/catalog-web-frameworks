import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from helpers import catalog, run_cli

# Throwaway repositories created by these tests are not signed and use a
# fixed test identity; they never leave the temporary directory.
GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
       "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"]

CONFIG = '{"framework": "%s", "tests": [{"default": {"json_url": "/json", "port": 8080}}]}'


class TempRepo:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.git("init", "-q")

    def git(self, *argv):
        return subprocess.run(GIT + list(argv), cwd=str(self.path), check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, rel, text):
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def framework(self, lang, name, dockerfile="FROM golang:1.22\n"):
        self.write("%s/%s/benchmark_config.json" % (lang, name), CONFIG % name)
        self.write("%s/%s/%s.dockerfile" % (lang, name, name), dockerfile)

    def commit(self, msg="c"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def close(self):
        self.tmp.cleanup()


class ChangedTest(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.repo.framework("Go", "gin")
        self.repo.framework("Go", "chi")
        self.repo.framework("Python", "flask")
        self.repo.write("README.md", "x\n")
        self.base = self.repo.commit("base")

    def tearDown(self):
        self.repo.close()

    def changed(self, *extra):
        return run_cli("--root", str(self.repo.path), "changed", "--since", self.base, *extra)

    def test_framework_change_lists_only_that_folder(self):
        self.repo.write("Go/gin/main.go", "package main\n")
        self.repo.commit()
        code, out, _ = self.changed()
        self.assertEqual(code, 0)
        self.assertEqual(out.split(), ["Go/gin"])

    def test_docs_only_change_lists_nothing(self):
        self.repo.write("README.md", "y\n")
        self.repo.write("docs/specs/x.md", "y\n")
        self.repo.commit()
        code, out, _ = self.changed("--json")
        self.assertEqual(json.loads(out), {"tooling": False, "folders": [], "matrix": []})

    def test_tooling_change_prints_all_tooling(self):
        for path in ("tools/catalog.py", "tests/test_x.py", ".github/workflows/ci.yml"):
            with self.subTest(path=path):
                repo = TempRepo()
                try:
                    repo.framework("Go", "go-std")
                    base = repo.commit()
                    repo.write(path, "x\n")
                    repo.commit()
                    code, out, _ = run_cli("--root", str(repo.path), "changed", "--since", base)
                    self.assertEqual(out.split(), [catalog.ALL_TOOLING])
                    _, out, _ = run_cli("--root", str(repo.path), "changed", "--since", base,
                                        "--json")
                    data = json.loads(out)
                    self.assertTrue(data["tooling"])
                    # Smoke sample entries that exist in this catalog are added.
                    self.assertEqual(data["matrix"], ["Go/go-std:default"])
                finally:
                    repo.close()

    def test_other_github_files_are_not_tooling(self):
        self.repo.write(".github/CODEOWNERS", "* @x\n")
        self.repo.commit()
        _, out, _ = self.changed()
        self.assertEqual(out.split(), [])

    def test_deleted_folder_is_not_listed(self):
        self.repo.git("rm", "-q", "-r", "Go/chi")
        self.repo.write("Python/flask/app.py", "print()\n")
        self.repo.commit()
        _, out, _ = self.changed()
        self.assertEqual(out.split(), ["Python/flask"])

    def test_root_in_subdirectory(self):
        repo = TempRepo()
        try:
            repo.write("catalog/Go/gin/benchmark_config.json", CONFIG % "gin")
            repo.write("catalog/Go/gin/gin.dockerfile", "FROM golang:1.22\n")
            base = repo.commit()
            repo.write("catalog/Go/gin/x.go", "x\n")
            repo.commit()
            code, out, _ = run_cli("--root", str(repo.path / "catalog"), "changed", "--since", base)
            self.assertEqual(out.split(), ["Go/gin"])
        finally:
            repo.close()


class LintDockerfileTest(unittest.TestCase):
    def lint(self, text):
        return catalog.lint_dockerfile(textwrap.dedent(text))

    def test_latest_fails(self):
        problems = self.lint("FROM ubuntu:latest\n")
        self.assertEqual(len(problems), 1)
        self.assertIn(":latest", problems[0][1])

    def test_untagged_fails(self):
        for image in ("ubuntu", "gcr.io/distroless/cc-debian12", "localhost:5000/img"):
            with self.subTest(image=image):
                self.assertEqual(len(self.lint("FROM %s\n" % image)), 1)

    def test_allowed_forms(self):
        text = """\
            # FROM ignored:latest
            ARG BASE=debian:12
            FROM --platform=linux/amd64 golang:1.22 AS build
            FROM build AS test
            FROM ${BASE}
            FROM $BASE AS other
            FROM scratch
            FROM python@sha256:0123456789abcdef
            FROM registry.example.com:5000/team/img:1.2.3 \\
                AS final
            from Build
            """
        self.assertEqual(self.lint(text), [])

    def test_alias_must_be_defined_before_use(self):
        problems = self.lint("FROM base\nFROM debian:12 AS base\n")
        self.assertEqual([p[0] for p in problems], [1])


class LintDockerCommandTest(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.repo.framework("Go", "gin", "FROM golang:latest\n")  # pre-existing, not linted
        self.repo.framework("Go", "chi")
        self.base = self.repo.commit()

    def tearDown(self):
        self.repo.close()

    def lint(self):
        return run_cli("--root", str(self.repo.path), "lint-docker", "--since", self.base)

    def test_unchanged_bad_dockerfile_is_ignored(self):
        self.repo.write("Go/chi/main.go", "x\n")
        self.repo.commit()
        code, out, _ = self.lint()
        self.assertEqual(code, 0)
        self.assertIn("0 Dockerfile(s) checked", out)

    def test_changed_dockerfile_with_latest_fails(self):
        self.repo.write("Go/chi/chi.dockerfile", "FROM golang:latest\n")
        self.repo.commit()
        code, out, _ = self.lint()
        self.assertEqual(code, 1)
        self.assertIn("Go/chi/chi.dockerfile:1: base image uses :latest", out)

    def test_added_untagged_dockerfile_fails(self):
        self.repo.write("Go/chi/chi-alt.dockerfile", "FROM alpine\n")
        self.repo.commit()
        code, out, _ = self.lint()
        self.assertEqual(code, 1)
        self.assertIn("untagged base image 'alpine'", out)

    def test_changed_tagged_dockerfile_passes(self):
        self.repo.write("Go/chi/chi.dockerfile", "FROM golang:1.23 AS b\nFROM scratch\n")
        self.repo.commit()
        code, _, _ = self.lint()
        self.assertEqual(code, 0)

    def test_deleted_dockerfile_is_ignored(self):
        self.repo.git("rm", "-q", "Go/gin/gin.dockerfile")
        self.repo.commit()
        code, _, _ = self.lint()
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
