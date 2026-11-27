FROM dlangdockerized/ldc:1.43.0@sha256:f2bdf2a920dbf8ce00ee4d848fb9d0c0f7d759e376aec4cec6aa549fcb8b20d6


WORKDIR /app

COPY . .

RUN apt-get update -yqq && apt-get install -yqq libpq-dev zlib1g-dev

RUN dub build -b release --compiler=ldc2

EXPOSE 8080

CMD ["/app/photon-http-benchmark"]

