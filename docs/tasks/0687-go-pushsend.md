# 0687: Go push delivery (pushsend) with DB tests
Status: todo
Depends on: 0683 steps 1-2 (commit 4a34744, go/internal/webpush) | Base commit: task/0683-go-push-sender | Branch: task/0683-go-push-sender (worktree /tmp/wt0683)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 80k tokens
## 1. Objective
Brief 0683 step 3 only: `go/internal/pushsend`, the Go port of `App/app/push.py` delivery, on top of the existing `go/internal/webpush`. Rules: 0683 section 2. The route and the job kind are brief 0688, not this one.
## 2. Context
Python: `App/app/push.py` constants (lines 25-50), `vapid_key`/`public_key`/`_subject` (72-105), `_hash` (107), `_clean_params`/`message` (254-266), `drain`/`send_test`/`_deliver`/`_settle`/`_retry`/`_finish` (311-460), `_drop` (203). `db.decrypt_secret`/`encrypt_secret`: `App/app/db.py` around 2290-2320 (find which Fernet key `_fernet()` uses; `go/internal/secure` `LoadDataKeys` mirrors `db._fernet`, check). `config.SUPPORT_EMAIL` and `config.WEB_PUSH` env names: grep `App/app/config.py`. Push catalog keys for `message`: see `host_i18n` keys used; add them to `go/internal/pushsend/i18n_keys.txt`, run `App/.venv/bin/python App/scripts/go_host_i18n.py` from `App/` (the .venv now exists), embed i18n.json, copy the loading pattern of `go/internal/pushweb`.
API: `type Sender struct{ Pool; Getenv; Now; Client *http.Client; AllowEndpoint func(string) bool }` (AllowEndpoint nil = webpush suffix check; tests set it to accept the httptest host). `Drain(ctx, limit) (map[string]int, error)`, `SendTest(ctx, accountID, endpoint) (string, error)`, `PublicKey(ctx) (string, error)`. Outcomes as Python strings: sent, gone, capped, retry, failed. Timestamps exactly `_stamp` format (UTC, seconds, `+00:00`). Payload JSON `json.dumps(..., ensure_ascii=False)` default separators; key order: message keys, then url, tag, lang.
## 3. Files
Create `go/internal/pushsend/pushsend.go`, `pushsend_test.go`, `i18n_keys.txt`, `i18n.json`. Small exports in `go/internal/webpush` if needed. Append a 0687 section to `docs/tasks/0683-report.md`.
## 4. Steps
1. Port. 2. DB tests (copy DB setup from `go/internal/pushweb/pushweb_test.go`), push service = httptest server: 201 -> sent, failures reset, last_sent_at set; 404/410 -> device + its outbox dropped; 429 and 500 -> retry at RETRY_MINUTES, past the last -> failed; 400 -> failed, failures+1, fifth -> dropped; 12 sent in 24 h -> capped; second claim of the same row updates 0 rows; transport error (closed server) -> retry; undecryptable keys -> gone; VAPID key created once and reused across two calls; unreadable VAPID setting -> outbox, subscriptions and setting deleted, new key; SendTest unknown endpoint -> gone; payload bytes received by the server decrypt (use a receiver key pair) to Python's JSON for a test message. 3. Commit `0687: Go push delivery` with the trailers you were given.
## 5. Do not touch
`App/` (read only), main.go, pushweb, CI, compose, `go.mod`/`go.sum`.
## 6. Commands
Own DB: `su postgres -c "createdb ubyhost0687" 2>&1 | tail -2`. From `/tmp/wt0683/go`: `test -z "$(gofmt -l .)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/ubyhost0687 go test ./internal/webpush/ ./internal/pushsend/ -count=1 -v 2>&1 | grep -E "^(--- |ok|FAIL)" | tail -40`. From `App/`: `.venv/bin/python scripts/go_host_i18n.py --check | tail -5`. Root: `python3 scripts/context_lint.py | tail -1`.
## 7. Acceptance
pushsend tests pass with the DB URL, 0 skipped; i18n check passes; no go.mod change.
## 8. Stop and ask
Schema change or new dependency needed. At 25 tool calls commit what builds and report what is left.
## 9. Report
0687 section in `docs/tasks/0683-report.md`: test tail, diff stat, differences from Python.
