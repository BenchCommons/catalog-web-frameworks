FROM postgres:19.0@sha256:4ea94de574c17f0372722806c949757050fbb1cd7648410fe45d6bba275cc00e

RUN mkdir -p /docker-entrypoint-initdb.d
COPY src/*.sql /docker-entrypoint-initdb.d/
