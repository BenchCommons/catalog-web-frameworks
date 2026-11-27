FROM debian:bookworm-slim as pre-build
RUN apt update
RUN apt upgrade -y
RUN apt install -y g++ curl make tar gzip libfindbin-libs-perl

FROM pre-build AS builder
WORKDIR /build
RUN sh -c "$(curl -sSL https://raw.githubusercontent.com/just-js/just/0.1.13/install.sh)"
RUN make -C just install
ENV JUST_HOME=/build/just
ENV JUST_TARGET=/build/just
WORKDIR /app
COPY techempower.js util.js tfb.config.js ./
RUN just build --clean --cleanall --static techempower.js

FROM gcr.io/distroless/static@sha256:4c2cd1dee442c9a99924a378c7c126fac8fef14771579ef567c3f2bdd7a5122a
WORKDIR /app
COPY --from=builder /app/techempower /app/techempower
COPY fortunes.html /app/fortunes.html
CMD ["./techempower"]
