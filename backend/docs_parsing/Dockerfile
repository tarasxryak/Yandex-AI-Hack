FROM golang:1.26-alpine AS build

WORKDIR /src

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/docs-parser ./cmd/docs-parser

FROM alpine:3.22

RUN apk add --no-cache ca-certificates \
	&& adduser -D -H -u 10001 appuser

COPY --from=build /out/docs-parser /usr/local/bin/docs-parser

USER appuser
EXPOSE 8080

ENTRYPOINT ["docs-parser"]
CMD ["-serve", ":8080"]
