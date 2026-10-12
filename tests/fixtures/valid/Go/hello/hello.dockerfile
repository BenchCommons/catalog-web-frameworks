FROM golang:1.22 AS build
FROM build AS final
CMD ["/app"]
