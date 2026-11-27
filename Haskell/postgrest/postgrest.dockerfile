FROM postgrest/postgrest:v16.6@sha256:5ce030c153500fe90ba157da4da8ba99ab51d3bc7b95e071bd0b544b67a632f7 AS builder

FROM alpine:3.24.4@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf
RUN apk add postgresql-client bash

COPY --from=builder /bin/postgrest /usr/local/bin/postgrest
COPY postgrest.conf /etc/postgrest.conf

ENV PGRST_DB_SCHEMA=public
ENV PGRST_DB_ANON_ROLE=
ENV PGRST_DB_POOL=100
ENV PGRST_DB_POOL_TIMEOUT=10
ENV PGRST_DB_EXTRA_SEARCH_PATH=public
ENV PGRST_DB_CHANNEL=pgrst
ENV PGRST_DB_CHANNEL_ENABLED=false
ENV PGRST_SERVER_HOST=*4
ENV PGRST_SERVER_PORT=3000
ENV PGRST_OPENAPI_SERVER_PROXY_URI=
ENV PGRST_JWT_SECRET=
ENV PGRST_SECRET_IS_BASE64=false
ENV PGRST_JWT_AUD=
ENV PGRST_MAX_ROWS=
ENV PGRST_PRE_REQUEST=
ENV PGRST_ROLE_CLAIM_KEY=.role
ENV PGRST_ROOT_SPEC=

ENV PGRST_DB_URI=postgres://benchmarkdbuser:benchmarkdbpass@tfb-database/hello_world
ENV PGRST_DB_SCHEMA=public
ENV PGRST_DB_ANON_ROLE=benchmarkdbuser
ENV PGRST_DB_POOL=64
RUN mkdir /app
COPY src /app
RUN chmod +x /app/entrypoint.sh
WORKDIR /app

EXPOSE 3000

ENTRYPOINT [ "/app/entrypoint.sh" ]
