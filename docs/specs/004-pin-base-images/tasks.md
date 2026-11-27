# Tasks — 004 Pin the existing Dockerfile base images

- [x] 1. Resolve index digests and matching tags for the 18 distinct images (plan §1).
- [x] 2. Replace the 38 unpinned `FROM` references (plan §2).
- [x] 3. Make the linter ignore a leading BOM, with a test (plan §3).
- [x] 4. `lint-docker --all` exits 0; `check` and unit tests pass.
- [x] 5. Stage A on affected variants with `database: none`, host arm64 (Docker 29.9.3). Pass: `C++/oatpp` (4), `D/archttp`, `Dart/{dart3,relic,shelf}:aot`, `Julia/oxygen`, `Rust/chopin`. `Fortran/fortran.io` is `skipped-broken`. `D/serverino` fails on arm64 and on `--platform linux/amd64` with `ld: cannot find -lz` in `dub build`. The pinned `alpine:3.24.4` digest equals today's `alpine:latest`, so the failure is not caused by pinning. Fixing it needs an `apk add` change, which R4 forbids here. A first run failed on a full host disk; those variants passed on rerun.
- [ ] 6. Follow-up PR for variants that cannot be verified without a database (#6) and for any variant whose Stage A result differs from the unpinned base.
  - Not run, database needed (#6): `C++/userver`, `D/photon-http`, `Go/fiber` (4), `Haskell/{ihp,postgrest}`, `R/plumber`, `Rust/ohkami` (4), and the mongodb variants `Rust/{axum,ignitia,rama}` (no Stage A types).
  - Declared `broken`, not run: `Haskell/wizzardo-inline`, `JavaScript/just`, `Julia/Jewelia`, `Nim/nim-stdlib`.
  - No catalog variant references them: `C++/ffead-cpp/ffead-cpp-rust-thruster`, `Haskell/postgrest/postgresql`, `Kotlin/http4k` (3 graalvm).
  - `D/serverino`: add static zlib to the apk list (separate change).
