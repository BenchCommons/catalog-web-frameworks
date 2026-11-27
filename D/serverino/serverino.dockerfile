FROM alpine:3.24.4@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf
RUN apk update && apk upgrade
RUN apk add gcc musl-dev ldc dub llvm-libunwind-static openssl-libs-static git make
RUN ln -fs /usr/share/zoneinfo/Europe/Rome /etc/localtime
RUN apk add tzdata
RUN apk cache clean

RUN adduser -D -S www-data

WORKDIR /app
COPY . .
RUN dub build --build=release-nobounds

EXPOSE 8080
USER www-data
CMD ["./serverino-benchmark"]
