FROM rust:1.93-slim-trixie AS builder

RUN apt update && apt install -y --no-install-recommends \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build/rt_smol
COPY ./Cargo.toml /build/
COPY ./src/       /build/src/
COPY ./rt_smol/  /build/rt_smol/
ENV RUSTFLAGS="-C target-cpu=native"
RUN cargo build --release

##########################################################

FROM gcr.io/distroless/cc-debian12@sha256:e5d81ddde149641e2a9ba55be4545bc125c67de07508b03ba4c22e6eb0ded5aa
COPY --from=builder /build/rt_smol/target/release/framework_benchmarks-smol /app/
EXPOSE 8000
CMD [ "/app/framework_benchmarks-smol" ]
