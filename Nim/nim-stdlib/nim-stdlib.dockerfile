FROM nimlang/nim:2.2@sha256:34bbc4d3d84137fd5da9ce50313268aaac48a7390185264027be0f3cf20848d9

ADD ./ /nimstdlib

WORKDIR /nimstdlib

RUN apt update && apt install -y libpq5

RUN nimble c --d:release --threads:on -y src/nimstdlib.nim -o:nimstdlib

EXPOSE 8080

CMD ./nimstdlib
