# 1630 report

Status: review

## 1. Files changed

- `go/internal/web/properties/lists.go`: `notPorted` sets `X-Ubyhost-Not-Ported: 1`
- `go/internal/web/properties/lists_test.go`: not-ported loop also checks the header
- `go/internal/web/properties/notported_test.go`: new, `TestNotPortedHeader`
- `deploy/lightsail/caddy/Caddyfile.cloudflare`: `@go_read` (GET/HEAD) block with `handle_response` fallback to Python
- `deploy/lightsail/caddy/Caddyfile.acme`: same block, `{remote_host}`
- `docs/ENVIRONMENT.md`: one sentence on the `UBYHOST_GO_PATHS` row
- `docs/tasks/1630-go-not-ported-fallback.md`: status set to review
- `docs/tasks/1630-report.md`: this file

## 2. Commands

- `cd go && go build ./...`: no output (clean)
- `cd go && go vet ./internal/web/properties/...`: no output (clean)
- `gofmt -l internal/web/properties`: no output (clean)
- `go test -count=1 -run TestNotPortedHeader ./internal/web/properties/`: `ok`
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55930/postgres go test -count=1 -v ./internal/web/properties/...`: exit 0, last lines:
  ```
  2026/11/14 15:27:16 INFO ical_sync_run owner=130001 feeds=1 not_modified=0 unchanged=0 changed=1 errors=0
  2026/11/14 15:27:16 INFO ical_sync_run owner=130001 feeds=2 not_modified=0 unchanged=1 changed=0 errors=1
  --- PASS: TestSyncNow (0.77s)
  PASS
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties	9.899s
  ```
  PASS count 39, FAIL 0, SKIP 0. PostgreSQL 16 ran on port 55930 (throwaway, now stopped).
- Step 5 caddy validate: **not run**. `docker info` reports no daemon (`/var/run/docker.sock` missing). Left to CI and the owner.
- Acceptance greps: `X-Ubyhost-Not-Ported` in lists.go = 2; `handle_response @not_ported` = 1 per Caddyfile; `header_up CF-Connecting-IP` = 4 per Caddyfile; `method GET HEAD` = 1 per Caddyfile.

## 3. Section 7 acceptance

- [x] Steps 1, 2, 3, 4, 6 committed; report committed as `1630 report`
- [x] Header and handle_response greps as above
- [x] `header_up CF-Connecting-IP` = 4 per Caddyfile
- [x] `method GET HEAD` present in both Caddyfiles
- [x] `TestNotPortedHeader` passes; properties golden tests pass with 0 skipped
- [x] Only the section 3 files plus the brief change in the 1630 commits

## 4. Deviations

- Step 5 (caddy validate) not run: no Docker daemon in this environment. Not claimed as passed.
- Base drift: when I started, `go-wave3` was at 4e84f6a. While working, `go-wave3` moved to 68e4a67 (a merge of `worktree-agent-a2d44f048bbeef15f` with 1591 commits). My branch was not rebased. `git diff go-wave3..HEAD` therefore shows 1591 files as deleted; the 1630 commits themselves touch only the section 3 files. Rebase or merge onto the new go-wave3 before merging.
- Brief status: the brief said `Status: todo`; set to `Status: review` per section 9.

## 5. Questions

- Should the 1630 commits be rebased onto 68e4a67 before the orchestrator merges? I did not rewrite history.

## 6. Owner steps left

1. Check production `UBYHOST_GO_PATHS` for `/apartments` or `/entities` (brief owner step 1, urgent).
2. After merge and deploy: `cd /opt/ubyhost/deploy/lightsail && ./scripts/caddy-validate.sh`, then `docker compose up -d caddy`. This is the validation step I could not run.
3. Optional staging test of the fallback (brief owner step 3).
