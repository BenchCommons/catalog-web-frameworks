# 001 — Bootstrap the web frameworks catalog

Issue: #1. Related: [.github#2](https://github.com/BenchCommons/.github/issues/2), [ADR 0004 in .product](https://github.com/BenchCommons/.product/blob/main/docs/adr/0004-continue-techempower-benchmarks.md), [benchmark-tool#29](https://github.com/BenchCommons/benchmark-tool/issues/29) (catalog contract), [dataset-tool#1](https://github.com/BenchCommons/dataset-tool/issues/1) (input contract). Tracking: [catalog-algorithms#11](https://github.com/BenchCommons/catalog-algorithms/issues/11).

## Context

TechEmpower sunset the TechEmpower Framework Benchmarks (TFB) on 2026-03-24 ([FrameworkBenchmarks#10932](https://github.com/TechEmpower/FrameworkBenchmarks/issues/10932)) and archived `TechEmpower/FrameworkBenchmarks`. FrameworkBenchmarks, TFBVerifier and TFBDatabases are BSD-3-Clause (© TechEmpower, Inc.). ADR 0004 proposes that BenchCommons continue the project. Under that proposal this repo receives the framework implementations with their history and adapts them to the org catalog contract.

The upstream state this spec is based on is the archived HEAD `57d92fbec6f8fd7431bc77326dd0484e60c96e20` (2026-03-23):

| Upstream fact | Value |
|---|---|
| Language folders under `frameworks/` | 41 |
| Framework folders (`frameworks/<Language>/<framework>/benchmark_config.json`) | 407 |
| Test variants (entries in `tests[]`) | 965 |
| Variants tagged `broken` | 160 |
| Dockerfiles (`*.dockerfile`) | 1016 |
| `FROM` lines pinned by digest | 0 of 1323 (14 use `:latest`; about 45 have no tag, not counting `scratch`) |
| Frameworks that also ship the newer `config.toml` | 323 |

Test-type coverage across the 965 variants:

| Test type | URL key | Variants | Needs a database |
|---|---|---|---|
| json | `json_url` | 674 | no |
| plaintext | `plaintext_url` | 664 | no |
| db (single query) | `db_url` | 669 | yes |
| queries (multiple queries) | `query_url` | 652 | yes |
| fortunes | `fortune_url` | 655 | yes |
| updates | `update_url` | 606 | yes |
| cached-queries | `cached_query_url` | 140 | yes |

Declared databases (case-insensitive; upstream mixes `Postgres`, `postgres`, `MySQL`, `Mysql` and so on): Postgres 507, MySQL 209, None 203, MongoDB 46.

## Goal

Make this repo the maintained home of the TFB framework implementations under BenchCommons. That means importing them with history and correct attribution, defining which test types the catalog supports and in what order, and checking every changed implementation for correctness in CI.

## Terms

- **Framework folder**: `<Language>/<framework>/`, one `benchmark_config.json` and one or more Dockerfiles.
- **Variant**: one entry in `tests[]`, such as `default`, `scratch` or `gorm` in `Go/gin`. A variant is the catalog's *implementation* unit: one image, one port, a set of test-type URLs and one database.
- **Test type**: one of the seven endpoints above. Each one has its own correctness rules.

## Requirements

### R1. Import source and layout
1. The import source is the archived upstream `TechEmpower/FrameworkBenchmarks`, pinned to the commit above. The removed `BenchCommons/FrameworkBenchmarks` fork is not used.
2. Only `frameworks/` is imported, with its full history. Upstream `toolset/`, `Dockerfile`, `entrypoint.sh`, `tfb` and the upstream `.github/` are not imported, because benchmark-tool is the toolset.
3. After the import, language folders sit at the repo root (`<Language>/<framework>/`), the same layout as `catalog-ssg`. benchmark-tool already mounts a catalog at its `frameworks/` path, so no path is renamed.
4. The maintainer runs the import (see plan). This spec and its PR do not contain upstream code.

### R2. License, attribution and no endorsement
1. Upstream `LICENSE` is kept verbatim as `LICENSE-TechEmpower` at the repo root. Imported files stay under it.
2. A `NOTICE` file credits the original project with its name, URL, copyright line, pinned commit and import date. It states that BenchCommons continues the archived project and is not affiliated with or endorsed by TechEmpower, Inc.
3. The README has an "Origin and attribution" section with the same facts and a link to `NOTICE`.
4. BSD-3-Clause clause 3 is respected everywhere: the README, the org profile, release notes, results and the website. The project is described only as "continuing the archived TechEmpower Framework Benchmarks". It never uses TechEmpower's name, logo or round results to promote BenchCommons and never implies endorsement. Results produced by BenchCommons are never labeled as TFB rounds.
5. New BenchCommons files are licensed BSD-3-Clause in a repo-level `LICENSE` with BenchCommons contributors as copyright holders. This keeps one license family in the repo. Imported files keep their original notice.

### R3. Test types and order
The catalog supports all seven TFB test types, in three stages:

| Stage | Test types | Why this order | Delivered by |
|---|---|---|---|
| A | json, plaintext | No external input. They cover about 70% of variants and can be verified on hosted CI today. | this spec |
| B | db, queries, fortunes, updates | Need the `World`/`Fortune` data as a pinned `dataset-*` input (R6). | follow-up spec 002 |
| C | cached-queries | Only 140 of 965 variants implement it. Its verifier relies on query counting through the database. | follow-up spec 003 |

Stage B and C URLs stay in the imported metadata unchanged, so no later re-import is needed. Until their stage lands, the catalog lists them as *declared, not verified*.

### R4. Mapping onto the catalog contract
The catalog contract (per-implementation layout, metadata schema, pinned Dockerfile, canonical runner, correctness check, result markers) is owned and specified by benchmark-tool in [benchmark-tool#29](https://github.com/BenchCommons/benchmark-tool/issues/29). This spec does not redefine it. It only says which TFB artifact feeds each part of the contract:

| Contract element (benchmark-tool#29) | TFB source in this repo | Adaptation here |
|---|---|---|
| Per-implementation layout | `<Language>/<framework>/` folder; variant = `tests[].<key>` | None. One framework folder can hold several implementations (variants). |
| Metadata schema | `benchmark_config.json` (`framework`, `maintainers`, `tests[].<key>` with `*_url`, `port`, `approach`, `classification`, `database`, `language`, `orm`, `platform`, `webserver`, `os`, `database_os`, `display_name`, `versus`, `tags`, optional `dockerfile`) | `benchmark_config.json` stays the source of truth. If the contract asks for another format, an adapter generates it, and CI fails when the generated output is stale. `config.toml` is upstream's partial duplicate. It is kept as imported and is not authoritative. |
| Pinned Dockerfile | `<framework>.dockerfile` for `default`, `<framework>-<key>.dockerfile` for other variants, or the `dockerfile` override (23 configs) | New or changed Dockerfiles may not use `:latest` or untagged base images. Digest pinning of all 1016 Dockerfiles follows the contract once it is defined (follow-up spec). |
| Canonical runner | The image's `CMD`/`ENTRYPOINT`, serving HTTP on `port` | None. The runner starts the container and waits for the port. |
| Correctness check | TFB verifier per test type (R5) | Runs untimed before any measurement and gates CI. |
| Result markers | None (TFB parses `wrk` output) | Supplied by benchmark-tool and perfratio, not by implementations. |

If benchmark-tool#29 lands with requirements this table cannot meet, this repo changes its adapter, not the contract.

### R5. Correctness verification per test type
Correctness follows the TFB verifier. The behavioral reference is the Python verifier in `toolset/test_types/` at the pinned upstream commit, which upstream CI used until the archive. TFBVerifier (Rust, last pushed 2022-02) is the structural reference for running the verifier as an isolated container. Where the two disagree, the Python verifier at the pinned commit wins.

Common checks for every test type: HTTP 200; `Server`, `Date` and `Content-Type` headers present; `Content-Length` or `Transfer-Encoding` present; `Date` in RFC 7231 format and not cached across requests; a non-empty body; and a route of at least the upstream minimum length.

| Test type | Stage | Passes when |
|---|---|---|
| json | A | `Content-Type: application/json` (optional `charset=utf-8`); the body is a JSON object `{"message": "Hello, World!"}`, with a case-insensitive value. Extra keys produce a warning. |
| plaintext | A | `Content-Type: text/plain` (optional `charset=utf-8`); the body contains `Hello, World!` (case-insensitive). Extra bytes produce a warning. |
| db | B | JSON object whose `id` and `randomNumber` are integers (keys case-insensitive). An `id` outside 1..10000, a `randomNumber` above 10000, extra keys or a single-element array produce warnings. The number of queries and rows read against `World`, counted on the database, matches the expected count within the upstream margin. |
| queries | B | `queries=N` returns an array of N `World` objects, clamped to 1..500. `0`, `foo` and an empty value return 1 object; `501` returns 500 (warning-level case). The query count matches. |
| fortunes | B | `Content-Type: text/html; charset=utf-8`; the HTML table matches the reference after the runtime row "Additional fortune added at request time." is added, rows are sorted by message and the content is HTML-escaped. The query and row counts match (12 rows per request in the dataset). |
| updates | B | Same cases as queries. In addition, for `queries=500` the rows are persisted with new `randomNumber` values, checked by reading `World` before and after. Batch updates are accepted within the upstream margin. |
| cached-queries | C | Same response shape and cases as queries. The route is at least `/cached-worlds/` long. |

A variant passes only if every test type it declares passes for the current stage. Warnings are reported but do not fail.

### R6. Databases as a `dataset-*` input
1. The `World` (10,000 rows) and `Fortune` (12 rows) tables and the Postgres, MySQL and MongoDB images come from TFBDatabases. Following .github#2, they move to a dataset repo (proposed name: `dataset-web-databases`) built and released through `dataset-tool` under the input contract of [dataset-tool#1](https://github.com/BenchCommons/dataset-tool/issues/1). This catalog only references that contract.
2. Upstream seeds `World.randomNumber` with `random()` when the database is created, so every run has different data. The dataset release must ship a fixed, seeded table with a checksum. The verifier checks values against that range, never against fixed values.
3. Database engine versions are pinned by the dataset release, not by implementations. Implementations keep the `database` field. Matching is case-insensitive, and the adapter normalizes it to `postgres`, `mysql`, `mongodb` or `none`.
4. Stage B cannot start until a dataset release exists. This spec does not create the dataset repo.

### R7. CI
1. On pull requests, only the variants of changed framework folders are built and verified, for stage A test types. A variant tagged `broken` is skipped and reported, not failed.
2. Changes under `tools/` (repo scripts) or `.github/workflows/` trigger the tooling tests plus a fixed smoke sample of variants, not the full catalog.
3. A metadata check runs on every PR for the whole catalog: each `benchmark_config.json` parses, and each variant has a Dockerfile that exists, a port and at least one URL. It covers all 407 configs without building images.
4. A full verification of all non-broken variants runs on a schedule (weekly) and on `workflow_dispatch`, sharded by language. `workflow_dispatch` accepts an explicit list of framework folders. This replaces upstream's `[ci fw-only …]` commit-message directives, which are not carried over.
5. Hosted CI only verifies correctness. It never produces published measurements (AGENTS.md: energy needs bare metal).

### R8. Broken variants
The 160 upstream variants tagged `broken` are imported unchanged. They are excluded from CI and from any measurement. They are listed in a tracking issue so they can be fixed or removed later, one list approved at a time.

## Acceptance criteria

1. `git log --follow` on any imported file shows upstream commits whose author and date are preserved. The folder count (407) and variant count (965) match the pinned commit.
2. `LICENSE-TechEmpower` matches upstream `LICENSE` byte for byte. `NOTICE` and the README's "Origin and attribution" section exist and contain the pinned commit. `grep -ri techempower` over README, NOTICE and docs finds no wording that implies endorsement or affiliation.
3. No upstream file outside `frameworks/` is present in the repo.
4. A PR that touches one framework folder builds and verifies only that folder's non-broken variants, for json and plaintext, and passes or fails on the R5 rules.
5. A PR that touches no framework folder and no tooling runs only the metadata check.
6. The metadata check fails on a config with a missing Dockerfile or no URLs, shown by a test fixture.
7. The scheduled full run produces a per-variant summary: pass, fail, warn, skipped as broken, declared but not yet verified.
8. A Dockerfile added or changed in a PR that uses `:latest` or an untagged base image fails CI.
9. `AGENTS.md` describes the stack, the layout, the verify command and the attribution rule.

## Out of scope

- Running full benchmark rounds or publishing measurements of any kind.
- The results website and any TFB-style results pages (website#5).
- Defining the catalog contract (benchmark-tool#29) or the input contract (dataset-tool#1).
- Creating `dataset-web-databases` or forking TFBVerifier, TFBToolset or tfb-status.
- Stage B and C verification (follow-up specs 002 and 003).
- Pinning existing Dockerfiles by digest, fixing broken variants, or removing frameworks.
- Upstream `toolset/`, `wrk` load scripts and continuous-run scripts.

## Follow-up specs

- 002: database test types (db, queries, fortunes, updates) on the dataset release.
- 003: cached-queries.
- 004: Dockerfile pinning to the catalog contract.
