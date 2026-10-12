# catalog-web-frameworks

Web framework implementations measured by [BenchCommons](https://github.com/BenchCommons): **407 frameworks in 41 languages**, with 965 test variants.

## Layout

One folder per language, one folder per framework, the same way `catalog-ssg` is laid out:

```
<Language>/<framework>/
├── benchmark_config.json      # authoritative metadata: tests (variants), test URLs, port, database, approach…
├── <framework>.dockerfile      # image for the "default" variant
├── <framework>-<variant>.dockerfile
└── … source of the implementation
```

`benchmark_config.json` is the source of truth. `config.toml`, present in most upstream folders, is kept but not authoritative. Implementations follow the catalog contract owned by [benchmark-tool](https://github.com/BenchCommons/benchmark-tool) (spec 010, benchmark-tool#29).

Languages: C C++ CFML Clojure Crystal CSharp D Dart Elixir Erlang Fortran FSharp Go Groovy Haskell Java JavaScript Julia Kotlin Lisp Lua Luau Nim OCaml Pascal Perl PHP Prolog Python R Racket Ruby Rust Scala Swift TypeScript Ur V Vala VB Zig 

## Test types

Rolled out in stages ([spec 001](docs/specs/001-bootstrap/spec.md)):

1. **A:** `json` and `plaintext`, with no database.
2. **B:** `db`, `queries`, `fortunes` and `updates`, with a pinned `dataset-*` database.
3. **C:** `cached-queries`.

## Origin and attribution

The framework implementations were imported with their full history from [TechEmpower/FrameworkBenchmarks](https://github.com/TechEmpower/FrameworkBenchmarks) at commit `57d92fb`. TechEmpower, Inc. archived that repo after sunsetting the project on 2026-03-24.

Those files are Copyright (c) TechEmpower, Inc. and contributors, under the BSD-3-Clause license in [`LICENSE-TechEmpower`](LICENSE-TechEmpower). New BenchCommons files are under [`LICENSE`](LICENSE). See [`NOTICE`](NOTICE).

BenchCommons continues the archived TechEmpower Framework Benchmarks. It is **not affiliated with, sponsored by or endorsed by TechEmpower, Inc.**
