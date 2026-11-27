FROM rust:1.93-slim-trixie AS builder

RUN apt update && apt install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build/rt_tokio
COPY ./Cargo.toml /build/
COPY ./src/       /build/src/
COPY ./rt_tokio/  /build/rt_tokio/
ENV RUSTFLAGS="-C target-cpu=native"
RUN cargo build --release

##########################################################

FROM gcr.io/distroless/cc-debian12@sha256:e5d81ddde149641e2a9ba55be4545bc125c67de07508b03ba4c22e6eb0ded5aa
ENV DATABASE_URL=postgres://benchmarkdbuser:benchmarkdbpass@tfb-database/hello_world
ENV MAX_CONNECTIONS=56
ENV MIN_CONNECTIONS=56
COPY --from=builder /build/rt_tokio/target/release/framework_benchmarks-tokio /app/
EXPOSE 8000
CMD [ "/app/framework_benchmarks-tokio" ]
