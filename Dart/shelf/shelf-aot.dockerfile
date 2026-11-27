
FROM dart:3.11.0 AS build
WORKDIR /app

ARG MAX_ISOLATES=8

COPY pubspec.yaml .
COPY shelf_aot/bin/ bin/

RUN dart compile aot-snapshot bin/server.dart \
    --define=MAX_ISOLATES=${MAX_ISOLATES} \
    -o server.aot

FROM gcr.io/distroless/base-debian13@sha256:1eb7e763df3f75a0d0eab87368f04e1bc61ce268caf3f2cbae765fa8fd4fd3e8
WORKDIR /app

COPY --from=build /usr/lib/dart/bin/dartaotruntime /usr/lib/dart/bin/dartaotruntime
COPY --from=build /app/server.aot /app/server.aot

EXPOSE 8080

ENTRYPOINT ["/usr/lib/dart/bin/dartaotruntime", "/app/server.aot"]