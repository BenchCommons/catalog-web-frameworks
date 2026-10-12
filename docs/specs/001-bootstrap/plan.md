# Plan — 001 Bootstrap the web frameworks catalog

Spec: [spec.md](spec.md). Tasks: [tasks.md](tasks.md).

## 1. Import (run by the maintainer)

The import rewrites history, so it runs in a throwaway clone and reaches this repo through a pull request. It is never pushed to `main` directly.

```sh
# 1. Fresh, full, single-branch clone of the archived upstream. git filter-repo
#    refuses to rewrite a shallow or non-fresh clone, so nothing is checked out
#    or committed before step 3.
git clone --single-branch --branch master \
  https://github.com/TechEmpower/FrameworkBenchmarks.git tfb-import
cd tfb-import
test "$(git rev-parse HEAD)" = 57d92fbec6f8fd7431bc77326dd0484e60c96e20

# 2. Keep the license text before it is filtered out.
git show HEAD:LICENSE > ../LICENSE-TechEmpower

# 3. Keep only frameworks/ and move its content to the root.
git filter-repo --subdirectory-filter frameworks

# 4. Sanity checks against the spec: 407 configs, 41 language folders,
#    no root-level files.
ls */*/benchmark_config.json | wc -l
ls -d */ | wc -l

# 5. Bring the rewritten history into the catalog on a branch.
cd ../catalog-web-frameworks
git switch -c import/tfb-frameworks origin/main
git remote add tfb-import ../tfb-import
git fetch tfb-import master
git merge --allow-unrelated-histories --no-ff tfb-import/master \
  -m "feat: import TFB frameworks/ from TechEmpower/FrameworkBenchmarks@57d92fb"
git remote remove tfb-import
```

Notes:

- Upstream commits keep their original authors and dates. `git filter-repo` preserves them, and the maintainer does not rewrite them. The maintainer's own commits (the merge and the attribution commit) are signed as usual.
- No path collides with `main`: `README.md` and `AGENTS.md` exist only at the root of this repo, and upstream `frameworks/` has no root-level files. Step 4 confirms this before the merge.
- **The import PR must be merged with a merge commit, not squash or rebase**, or the history is lost. The maintainer enables "Allow merge commits" for this PR if the repo setting is off.
- Upstream history is large. The merge is pushed once, and later PRs are normal.
- The throwaway clone is deleted after the PR merges, after listing it and getting approval (AGENTS.md, Safety).

## 2. Attribution commit (same PR, after the merge)

- `LICENSE-TechEmpower`: the file saved in step 2, unchanged.
- `LICENSE`: BSD-3-Clause, "Copyright (c) 2026, BenchCommons contributors", for new files.
- `NOTICE`:
  - "This repository contains framework implementations imported from TechEmpower/FrameworkBenchmarks (https://github.com/TechEmpower/FrameworkBenchmarks), commit 57d92fbec6f8fd7431bc77326dd0484e60c96e20, archived by TechEmpower, Inc. after the project was sunset on 2026-03-24."
  - "Those files are Copyright (c) TechEmpower, Inc. and contributors and are distributed under the BSD-3-Clause license in LICENSE-TechEmpower."
  - "BenchCommons continues the archived TechEmpower Framework Benchmarks. It is not affiliated with, sponsored by or endorsed by TechEmpower, Inc."
- README "Origin and attribution" section: the same three facts, plus a link to `NOTICE`. The rest of the README never uses the TechEmpower name as a selling point.

## 3. Repo tooling (`tools/`)

One stdlib-only Python 3 entry point, `tools/catalog.py`, written from scratch (no upstream toolset code). Its unit tests live in `tests/` with small fixture catalogs.

| Command | Does |
|---|---|
| `catalog.py check` | Parses every `*/*/benchmark_config.json` and resolves each variant's Dockerfile (`<framework>.dockerfile` for `default`, `<framework>-<key>.dockerfile` otherwise, or the `dockerfile` override). It requires a port and at least one known `*_url`, normalizes `database`, and reports test types per stage. Exit code 1 on errors. |
| `catalog.py list [--lang L] [--json]` | Lists variants as `Language/framework:key`, with stage-A test types and the `broken` flag. |
| `catalog.py changed --since <ref>` | Lists changed framework folders from `git diff --name-only <ref>...HEAD`. Prints `ALL_TOOLING` when `tools/`, `tests/` or `.github/workflows/` change. |
| `catalog.py lint-docker --since <ref>` | Fails if a changed `*.dockerfile` has a `FROM` with `:latest` or no tag. Stage aliases, `scratch` and `ARG`-substituted images are allowed. |
| `catalog.py verify <Language/framework[:key]> [--stage A]` | For each non-broken variant: `docker build -f <dockerfile> <folder>`, run it on a private network, wait for the port (timeout 120 s), run the stage's verifiers, then stop and remove the container. Prints one result line per test type: pass, warn, fail, or declared-not-verified. |

Verifier design for stage A: `tools/verify/` implements the json and plaintext rules and the common header rules from spec R5, as a clean-room implementation of the documented behavior. It sends the same request twice, 3 s apart, for the `Date` check. Fixture tests cover each pass, warn and fail rule with a local stub HTTP server. Spec 002 decides whether stages B and C use a fork of TFBVerifier, since query counting needs database access. The verifier is called through one function, so swapping it out does not touch the CLI or CI.

Contract adapter: once benchmark-tool#29 defines the metadata format, `catalog.py export` generates it from `benchmark_config.json`. `check` then also fails when the generated files are stale. Until then, benchmark-tool reads `benchmark_config.json` directly, as it already does for catalog-ssg.

## 4. CI (`.github/workflows/ci.yml`)

| Job | Trigger | Runs |
|---|---|---|
| `metadata` | every PR and push | `catalog.py check` over the whole catalog; unit tests in `tests/` |
| `changed` | PR | `catalog.py changed --since <base sha>` and `lint-docker`. Outputs a matrix of framework folders |
| `verify` | PR, when `changed` is non-empty | Matrix by framework folder, `fail-fast: false`, `catalog.py verify <folder> --stage A`. For `ALL_TOOLING`, a fixed smoke sample instead (e.g. `C/h2o`, `Go/gin`, `Java/spring`, `JavaScript/express`, `Python/flask`, `Rust/actix`) |
| `full` | weekly `schedule`, `workflow_dispatch` (input: space-separated folders, empty means all) | Matrix by language (41 shards, `max-parallel` bounded), all non-broken variants, stage A. Uploads a JSON summary artifact and writes a job summary |

- `actions/checkout` with `fetch-depth: 0` in `changed` so the merge base is available.
- `ubuntu-24.04` runners, with Docker preinstalled. Stop any preinstalled MySQL or Postgres services so they do not hold ports.
- Upstream's commit-message directives and its `get-maintainers` and `ping-maintainers` workflows are not carried over. Ownership through the `maintainers` field can be revisited in a later spec.
- Retries: one retry for `docker build` network failures, never for verification failures, and listed in the summary (same approach as catalog-algorithms 008).

## 5. Decisions

- **Root layout, as in catalog-ssg.** `--subdirectory-filter frameworks` already produces it, and benchmark-tool mounts catalogs at `frameworks/`.
- **`benchmark_config.json` is authoritative; `config.toml` is not.** Every upstream framework has the JSON file, only 323 of 407 have the TOML, and the upstream toolset reads the JSON.
- **Stage A first.** It is verifiable on hosted CI with no external input and unblocks the import and CI loop while dataset-tool#1 is specified.
- **Clean-room stage-A verifier.** It is about 100 lines of logic and avoids adopting a 2022 Rust codebase before spec 002 evaluates it.
- **No measurement here.** Load generation (`wrk`) and results belong to benchmark-tool and perfratio.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Many variants fail on current base images or package mirrors (archived and unmaintained since 2026-03) | Failures in `full` are reported, not blocking. The tracking issue lists them. A variant is marked `broken` only by an explicit, reviewed PR. |
| A full run is too slow for hosted CI (965 variants, ~1000 builds) | Language shards, weekly cadence, and only stage-A test types. |
| Accidental endorsement wording in later docs or the website | Acceptance check 2 (grep). The rule is copied into `AGENTS.md`. |
| A squash merge drops the imported history | The §1 note, plus a check after merging: `git log --follow` on an imported file shows upstream commits (acceptance criterion 1). |
| The contract (benchmark-tool#29) lands with different fields | Only the adapter (`catalog.py export`) changes. Implementations do not. |
