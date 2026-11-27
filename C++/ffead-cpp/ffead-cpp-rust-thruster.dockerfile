FROM sumeetchhetri/ffead-cpp-rust-base:6.0@sha256:323f7ffbd43b988defa717a8b376281aaff83bae2cfeeddc57b368841b1321cf

ENV IROOT=/installs

WORKDIR /

CMD ./run_ffead.sh ffead-cpp-6.0 rust-thruster
