# Tasks — 001 Bootstrap the web frameworks catalog

Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Each task is one PR, or one commit inside the noted PR, and can be checked on its own.

## PR 1 — Import (maintainer)
- [ ] 1.1 Run plan §1 steps 1–4. Confirm 407 configs, 41 language folders and HEAD `57d92fb` before filtering. (Spec R1)
- [ ] 1.2 Merge the rewritten history on `import/tfb-frameworks` (plan §1 step 5).
- [ ] 1.3 Attribution commit: `LICENSE-TechEmpower`, `LICENSE`, `NOTICE` and the README "Origin and attribution" section (plan §2). (Spec R2)
- [ ] 1.4 Check: `cmp` against upstream `LICENSE`; `grep -ri techempower README.md NOTICE docs/` shows only attribution wording; no upstream `toolset/` or root files present. (Acceptance 2, 3)
- [ ] 1.5 Open the PR and merge it **with a merge commit**. After merging, run `git log --follow` on an imported file. (Acceptance 1)
- [ ] 1.6 Open a tracking issue listing the 160 `broken` variants. (Spec R8)
- [ ] 1.7 After listing it and getting approval, delete the throwaway `tfb-import` clone.

## PR 2 — Metadata tooling
- [ ] 2.1 `tools/catalog.py check` and `list`, with Dockerfile resolution and `database` normalization. (Plan §3)
- [ ] 2.2 Fixture catalogs in `tests/`: valid; missing Dockerfile; no URLs; `dockerfile` override; `broken` tag. (Acceptance 6)
- [ ] 2.3 `check` passes on the full imported catalog. Its counts match the spec (407 / 965).

## PR 3 — Change detection and Dockerfile lint
- [ ] 3.1 `catalog.py changed --since <ref>`, including the `ALL_TOOLING` rule. Tests with a temporary git repo.
- [ ] 3.2 `catalog.py lint-docker --since <ref>`. Tests: `:latest` fails, an untagged image fails, `scratch`, stage aliases and a tagged image pass. (Acceptance 8)

## PR 4 — Stage A verifier
- [ ] 4.1 `tools/verify/` common header checks: status, `Server`, `Date` (format and not cached), `Content-Type`, size header. (Spec R5)
- [ ] 4.2 json and plaintext rules, each pass, warn and fail case covered by a stub HTTP server fixture.
- [ ] 4.3 `catalog.py verify <folder>[:key] --stage A`: build, run, wait for the port, verify, clean up. Stage B and C types are reported as declared-not-verified.
- [ ] 4.4 Manual run on the smoke sample (plan §4). Record the results in the PR description.

## PR 5 — CI
- [ ] 5.1 `.github/workflows/ci.yml` with `metadata`, `changed`, `verify` and `full` jobs (plan §4). (Spec R7)
- [ ] 5.2 Test PR touching one framework folder: only that folder's variants run. (Acceptance 4)
- [ ] 5.3 Test PR touching only docs: only `metadata` runs. (Acceptance 5)
- [ ] 5.4 `workflow_dispatch` full run: the summary artifact lists pass, fail, warn, skipped-broken and declared-not-verified per variant. (Acceptance 7)

## PR 6 — Docs
- [ ] 6.1 `AGENTS.md`: stack, layout, `catalog.py` commands, verify runbook, attribution and no-endorsement rule. (Acceptance 9)
- [ ] 6.2 README: catalog overview, stages, how to add a framework. Uses the BenchCommons flow, not the upstream scaffolding text.
- [ ] 6.3 `docs/specs/ROADMAP.md` listing 001 and the follow-up specs 002–004.
