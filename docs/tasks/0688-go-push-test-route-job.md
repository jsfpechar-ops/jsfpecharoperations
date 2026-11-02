# 0688: Go push test route and push job kind
Status: todo
Depends on: 0687 | Base commit: task/0683-go-push-sender | Branch: task/0683-go-push-sender (worktree /tmp/wt0683)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 70k tokens
## 1. Objective
Brief 0683 steps 4-5: `POST /account/push/test` in `go/internal/pushweb` using `pushsend.Sender.SendTest`, and job kind `push` (runs `Drain(ctx, 50)`) in `go/cmd/ubyhost-web/main.go` `goHandlers` with interval 60 s (see how `ical` registers its interval). Off when Python's `enabled()` is off (same env var).
## 2. Context
Python: `App/app/routes/push.py` `push_test` (115-128), `own_account`, `_error`, `_answer`, `_text`, `_body`, `TEST_MAX_PER_HOUR`; `App/app/rate_limit.py` `blocked`, `record` (port as a small private helper on the same table and key strings if Go has none: grep `rate_limit` in `go/internal`); `App/app/scheduler.py` `_job_push` (386-398). Existing pushweb handlers show the guard, CSRF and JSON error shape: reuse them. If pushweb's `/account/push/subscribe` returns `public_key`, check it still matches `pushsend.PublicKey`.
## 3. Files
Edit `go/internal/pushweb/pushweb.go` (+ `pushweb_test.go`, i18n keys if new), `go/cmd/ubyhost-web/main.go`. Append a 0688 section to `docs/tasks/0683-report.md`; set 0683, 0687, 0688 Status lines to review.
## 4. Steps
1. Route + job kind. 2. Tests (DB, httptest push service): signed out 401; 11th test in an hour 429 (check TEST_MAX_PER_HOUR); push service 500 -> 502 with Python's error JSON; success JSON `{"ok": true, "message": ...}` byte-identical to Python's (check how pushweb already encodes Python JSON); `parseGoKinds("push")` accepted. 3. Commit `0688: Go push test route and push job` with the trailers you were given.
## 5. Do not touch
`App/`, CI, compose, Caddy, `go.mod`/`go.sum`, packages other than pushweb, pushsend (bug fixes only) and main.go.
## 6. Commands
Own DB: `su postgres -c "createdb ubyhost0688" 2>&1 | tail -2`. From `/tmp/wt0683/go`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/ubyhost0688 go test ./internal/webpush/ ./internal/pushsend/ ./internal/pushweb/ ./cmd/... -count=1 2>&1 | tail -30`. From `App/`: `.venv/bin/python scripts/go_host_i18n.py --check | tail -5`. Root: `python3 scripts/context_lint.py | tail -1`.
## 7. Acceptance
All listed packages pass with the DB URL, 0 skipped; vet/gofmt/build clean.
## 8. Stop and ask
Schema change or new dependency needed.
## 9. Report
0688 section in `docs/tasks/0683-report.md`.
