# Build context is the repository root (see deploy/lightsail/docker-compose.yml).
FROM golang:1.26-alpine@sha256:ecb67f987aa1a57794c91d19ade7ae0209f2f0f5496aaef9e6ae85ddf92d02ab AS builder
ARG GIT_SHA=dev
WORKDIR /src
COPY go/go.mod go/go.sum ./
RUN go mod download
COPY go/ ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w -X main.version=${GIT_SHA}" -o /out/ubyhost-web ./cmd/ubyhost-web

FROM alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a
RUN adduser -D -u 10001 ubyhost
COPY --from=builder /out/ubyhost-web /usr/local/bin/ubyhost-web
COPY App/migrations_pg/ /app/migrations_pg/
COPY App/app/static/ /app/static/
ENV UBYHOST_GO_ADDR=0.0.0.0:8081 UBYHOST_MIGRATIONS_DIR=/app/migrations_pg UBYHOST_APP_ROOT=/app
USER ubyhost
EXPOSE 8081
ENTRYPOINT ["/usr/local/bin/ubyhost-web"]
