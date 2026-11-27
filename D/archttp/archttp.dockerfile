FROM dlang2/ldc-ubuntu:1.26.0@sha256:445f1745615e16b0a38af4c257ae79987a2fc274d77603aec550e621a1eb5f50

ADD ./ /archttp
WORKDIR /archttp

RUN apt-get update -yqq && apt-get install -yqq zlib1g-dev

RUN dub build -b release --compiler=ldc2 --verbose

EXPOSE 1111

CMD ["./archttp-server"]
