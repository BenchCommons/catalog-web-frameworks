FROM nixos/nix:2.36.0@sha256:746280551ddc1c72177d1a597c05eacac86dfaa18d5d649bf86411278bcd5470
MAINTAINER Facundo Dominguez <facundo.dominguez@tweag.io>

USER root
WORKDIR /wizzardo-inline

COPY nixpkgs.nix nixpkgs.nix
COPY shell.nix shell.nix

RUN nix-shell --run "echo Fetched dependencies"

COPY wizzardo-http-benchmark wizzardo-http-benchmark
COPY BUILD.bazel BUILD.bazel
COPY WORKSPACE WORKSPACE
COPY .bazelrc .bazelrc
COPY snapshot-9.0.2.yaml snapshot-9.0.2.yaml

RUN nix-shell --run "bazel build //wizzardo-http-benchmark"

EXPOSE 8080

CMD nix-shell --run "bazel-bin/wizzardo-http-benchmark/wizzardo-http-benchmark env=prod +RTS -A32m -N$(nproc) -RTS"
