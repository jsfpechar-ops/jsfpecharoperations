# 0475: Go G1b: the Go service runs in production as an internal container, serving no traffic yet
Status: review
Depends on: 0474 (merged) | Base commit: main | Branch: task/0475-go-g1b
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 70k tokens
## 1. Objective
Ship `go/cmd/ubyhost-web` as a container next to the Python app (plan v4 step 13, second half). It connects to production PostgreSQL over the shared socket, refuses to start while a goose file is pending, and answers `/healthz` on the compose network only. Caddy does not route to it yet (G2 flips routes). It must never be able to break a deploy or the running app: nothing depends on it, and deploy.sh only reports its health.
## 2. Context
- `deploy/lightsail/docker-compose.yml`: the `ubyhost` service (line 38) is the pattern: build context `../..`, socket volume `ubyhost-pgsock:/var/run/postgresql`, `mem_limit`, json-file logging, network `web`. `litestream` (line ~135) shows the pattern of passing only named variables instead of the whole `.env`.
- Production URL form (`deploy/lightsail/scripts/pg-cutover.sh` line 17): `postgresql://ubyhost@/ubyhost?host=/var/run/postgresql` (socket, no password). pgx understands `host=` in the query string.
- The Python image runs as uid 10001 (`Dockerfile`); the socket directory is shared, so the Go container runs as the same uid.
- `deploy/lightsail/scripts/deploy.sh` line ~268 prints `Health (internal):` for the Python app.
- `.dockerignore` excludes `docs/` and `*.md`, not `go/`.
- Base images, pinned by digest (looked up 2026-11-01): `golang:1.25-alpine@sha256:1ae0735f00daffa3aaf1363a5184c0d2dc55c78e3db4ec70241cdac97bf84b59`, `alpine:3.22@sha256:2e0b81d60597f449baa56dc25d355367869d2dca4cd57e866f1e2b52af3eb55f`.
## 3. Files
New: `go/Dockerfile`. Edit: `deploy/lightsail/docker-compose.yml` (one service), `deploy/lightsail/scripts/deploy.sh` (one block), `.github/workflows/ci.yml` (`docker` job, one step), `.github/dependabot.yml` (one docker entry for `/go`), `docs/LIGHTSAIL.md` (one row or line where services are listed). Write `docs/tasks/0475-report.md`.
## 4. Steps
1. `go/Dockerfile`, build context = repo root:
   - Builder `FROM golang:1.25-alpine@sha256:1ae0...` with `WORKDIR /src`. `COPY go/go.mod go/go.sum ./`, then `RUN go mod download`, then `COPY go/ ./`, then `RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/ubyhost-web ./cmd/ubyhost-web`.
   - Runtime `FROM alpine:3.22@sha256:2e0b...`, then `RUN adduser -D -u 10001 ubyhost`.
   - Copy `/out/ubyhost-web` to `/usr/local/bin/`, and `App/migrations_pg/` to `/app/migrations_pg/`.
   - Set `ENV UBYHOST_GO_ADDR=0.0.0.0:8081 UBYHOST_MIGRATIONS_DIR=/app/migrations_pg`, `USER ubyhost`, `EXPOSE 8081`, `ENTRYPOINT ["/usr/local/bin/ubyhost-web"]`.
2. `docker-compose.yml`, new service `ubyhost-go` after `worker`, with a two-line comment saying it is the Go port and serves no traffic until a Caddy route is added (G2):
   - `build: {context: ../.., dockerfile: go/Dockerfile}`, `image: ubyhost-go:local`, `restart: unless-stopped`, `stop_grace_period: 15s`.
   - `environment:` with only `UBYHOST_DATABASE_URL: ${UBYHOST_DATABASE_URL:-}`.
   - `volumes: [ubyhost-pgsock:/var/run/postgresql]`, `expose: ["8081"]`.
   - `healthcheck: test ["CMD", "wget", "-qO-", "http://127.0.0.1:8081/healthz"]`, interval 30s, timeout 5s, retries 3, start_period 15s.
   - `mem_limit: ${UBYHOST_GO_MEM:-128m}`, the same json-file logging block, `networks: [web]`.
   - `depends_on: {ubyhost: {condition: service_healthy}}` (goose is applied before the web app starts).
   - Add `profiles: ["go"]` so it starts only when `COMPOSE_PROFILES` contains `go`. With SQLite (`UBYHOST_DATABASE_URL` empty) it cannot run, and the owner turns it on with one `.env` line.
   - Nothing else may depend on it.
3. `deploy.sh`, after the `Health (internal):` block:
   - If `docker compose ps --status running --services | grep -qx ubyhost-go`, print `Go service (internal, no traffic yet):` followed by `docker compose exec -T ubyhost-go wget -qO- http://127.0.0.1:8081/healthz || echo "not healthy (does not affect the app)"`.
   - Otherwise print `Go service: not enabled (COMPOSE_PROFILES has no go)`.
   - This block never exits non-zero.
4. `ci.yml` `docker` job, one new step after `Build image`: `docker build -f go/Dockerfile -t ubyhost-go:ci .`, then `docker run --rm ubyhost-go:ci 2>&1 | grep -q UBYHOST_DATABASE_URL`. With no URL the binary must exit non-zero and name the missing variable. Read `go/cmd/ubyhost-web/main.go` for its exact message, and match that word.
5. `.github/dependabot.yml`: copy the existing docker entry with `directory: /go`.
6. `docs/LIGHTSAIL.md`: one line in the services list, and in the owner steps: "Go service: add `go` to `COMPOSE_PROFILES` in `.env` (for example `COMPOSE_PROFILES=go`, or append `,go`), then deploy. It serves nothing until G2."
## 5. Do not touch
`Caddyfile*`, `App/`, `go/` other than the new Dockerfile, existing compose services, every other part of deploy.sh.
## 6. Commands
From the repo root:
- `docker build -f go/Dockerfile -t ubyhost-go:test . 2>&1 | tail -5`. If Docker is not available locally, say so and rely on CI.
- `docker compose -f deploy/lightsail/docker-compose.yml config --quiet 2>&1 | tail -5`. A dummy `.env` may be needed: copy `deploy/lightsail/.env.example` to a temp dir and point `--env-file` at it.
- `bash -n deploy/lightsail/scripts/deploy.sh`.
- `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
The image builds in CI, and the run without a URL exits non-zero, naming the variable. `docker compose config` is valid. The service is behind the `go` profile, so production is unchanged until the owner adds the profile. deploy.sh passes `bash -n` and its new block cannot fail the deploy.
## 8. Stop and ask
Stop if a step needs a change in `App/`, in `go/` code, or in Caddy; or if a digest above fails to pull in CI.
## 9. Report
`docs/tasks/0475-report.md`: the command tails and the final compose service block.
