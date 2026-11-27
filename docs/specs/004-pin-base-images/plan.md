# Plan — 004 Pin the existing Dockerfile base images

Spec: [spec.md](spec.md).

## 1. Resolve

For each distinct unpinned image, `docker buildx imagetools inspect <image>:latest` gives the index digest (the implicit tag of an untagged `FROM` is `latest`). Docker Hub's tag list (`/v2/repositories/<repo>/tags`) gives the explicit tags with that digest. Pick the most specific one. For gcr.io and ghcr.io images the tag list showed no versioned tag with that digest, so only the digest is used.

## 2. Families

| Family | Files | New reference |
|---|---|---|
| alpine | `D/serverino`, `Go/fiber` (4), `Haskell/postgrest` | `alpine:3.24.4@sha256:f59abe65…` |
| distroless | Rust (9: axum, chopin, ignitia, ohkami x4, rama), Dart (3), `JavaScript/just` | `gcr.io/distroless/<name>@sha256:…` (digest only) |
| ffead | `C++/ffead-cpp/ffead-cpp-rust-thruster` | `sumeetchhetri/ffead-cpp-rust-base:6.0@…`. `:latest` does not exist in the registry |
| digest only | `C++/oatpp` (4), `C++/userver` | `lganzzzo/ubuntu-cmake-mimalloc@…`, `ghcr.io/userver-framework/ubuntu-22.04-userver-pg@…` |
| language/tool images | `D/archttp`, `D/photon-http`, `Fortran/fortran.io`, `Haskell/{ihp,wizzardo-inline,postgrest}`, `Julia/{Jewelia,oxygen}`, `Kotlin/http4k` (3), `Nim/nim-stdlib`, `R/plumber` | `repo:tag@digest`, see the diff |

The exact references are in the diff. Digests come from the same registry query that produced the tag, so the tag and the digest name one artifact.

## 3. Linter

`FROM_RE` accepts a leading `\ufeff`. One new test in `tests/test_changed_lint.py`.

## 4. Verify

`lint-docker --all`, `check`, `unittest`. Stage A (`verify --stage A`) on affected variants whose database is `none`, on the host's own architecture, or `linux/amd64` when the base image is amd64-only. Variants that need a database are not run (#6).
