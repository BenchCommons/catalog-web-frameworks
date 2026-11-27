# 004 — Pin the existing Dockerfile base images

Issue: #9. Related: #6 (Stage A database), #1, [tools-benchmark#29](https://github.com/BenchCommons/tools-benchmark/issues/29) (catalog contract, spec 010 R-4). Builds on [spec 001, R4](../001-bootstrap/spec.md): new or changed Dockerfiles may not use `:latest` or untagged bases, and pinning the 1016 existing ones is a follow-up.

## Context

At `9b58ea110`, `python3 tools/catalog.py lint-docker --all` exits 1 with 39 problems: 14 `:latest` and 25 untagged references, in 38 Dockerfiles (37 with a real unpinned reference, one of them with two). The PR workflow only lints changed files, so the backlog never failed CI. 38 of the 39 are real unpinned references. The 39th, `FROM base AS final` in `CSharp/celerio/celerio.dockerfile`, is a false positive: the file starts with a byte order mark, so the linter did not see its first `FROM ... AS base` and did not register the alias.

## Requirements

- **R1.** Each of the 38 real references names the exact artifact that the unpinned reference resolves to today, as `repo:tag@sha256:<index digest>` when the registry has an explicit non-`latest` tag with that same digest, and as `repo@sha256:<digest>` when it does not (the registry only has floating tags, or the only tag is `latest`).
- **R2.** The digest is the manifest list (index) digest when the image has one, so all published architectures are kept. No major version is changed to make a build pass. Where `latest` does not exist at all (`sumeetchhetri/ffead-cpp-rust-base`), the tag is the one every sibling Dockerfile in the same folder uses (`6.0`).
- **R3.** The linter ignores a leading byte order mark. A test covers it. Lint rules, CLI and CI are otherwise unchanged.
- **R4.** Only `FROM` lines change in Dockerfiles. Runner, metadata, `benchmark_config.json` and the central runner paths are untouched.
- **R5.** `lint-docker --all` exits 0, `catalog.py check` and the unit suite still pass. Stage A is run on the affected variants that need no database. The rest is recorded with the reason, not claimed.

## Out of scope

- The 977 Dockerfiles that already pass lint but pin only a tag. Digest pinning and `ARG *_VERSION` pins (spec 010 R-4) follow in the catalog adoption spec.
- Making the pinned images build or pass if they did not before. Variants that are already `broken` stay as they are.
- A lint in CI for the whole catalog (`--all`). It can be added once the backlog is zero, in a separate change.

## Acceptance

1. `python3 tools/catalog.py lint-docker --all` exits 0 with 0 problems.
2. `python3 tools/catalog.py check` reports 0 errors and the same counts as before (407 / 965 / 1016).
3. `python3 -m unittest discover -s tests -v` passes.
4. `git diff` outside `tools/`, `tests/` and `docs/` contains only `FROM` line changes.
5. Every pinned digest resolves in its registry (`docker buildx imagetools inspect <ref>`).
