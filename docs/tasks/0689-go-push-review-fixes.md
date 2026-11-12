# 0689: Go push review fixes
Status: done (code on main and live in production, server on #928, 2026-11-12; closed in bulk by the orchestrator)
Depends on: 0688 | Base commit: claude/project-thread-pw8sp2 | Branch: task/0689-go-push-review-fixes
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 50k tokens
## 1. Objective
Three review findings on PR #687, nothing else.
## 2. Context
1. `go/internal/webpush/webpush.go` `Send` builds its request without a context: add `ctx context.Context` as the first parameter, use `http.NewRequestWithContext`, pass the ctx from `pushsend` `deliver`.
2. `go/internal/pushsend/pushsend.go` `allowed()` checks only the host suffix, while save time (`go/internal/pushweb/pushweb.go` ~411-417, Python `clean_subscription`) also requires https, default port, no userinfo. Export one validator from `webpush` (e.g. `webpush.EndpointAllowed(raw string) bool`) with the full save-time rules and use it in both places; keep pushweb's error behaviour unchanged.
3. `pushsend` lacks Python's logs (`App/app/push.py` `_deliver`/`_settle`): add `log.Printf` lines `push_transport_error subscription=%d error=%v`, `push_unreadable_device subscription=%d`, `push_gone subscription=%d status=%d`, `push_refused subscription=%d status=%d kind=%s`. Never log the endpoint or keys.
## 3. Files
`go/internal/webpush/webpush.go` (+ test), `go/internal/pushsend/pushsend.go` (+ test call sites), `go/internal/pushweb/pushweb.go`. Write `docs/tasks/0689-report.md`.
## 4. Steps
Make the three changes, add a unit test for the validator (http, port 8080, userinfo, bad suffix refused; fcm https allowed), commit `0689: Go push review fixes` with the trailers you were given.
## 5. Do not touch
Everything else.
## 6. Commands
Own worktree: `git worktree add -b task/0689-go-push-review-fixes /tmp/wt0689 origin/claude/project-thread-pw8sp2`. From `/tmp/wt0689/go`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/webpush/ ./internal/pushsend/ ./internal/pushweb/ ./cmd/... -count=1 2>&1 | tail -20`. Root: `python3 scripts/context_lint.py | tail -1`.
## 7. Acceptance
Tests pass (DB tests skip locally; they run in CI), vet and gofmt clean.
## 8. Stop and ask
If a test in pushsend relies on the suffix-only check for its httptest server, keep the injectable `AllowEndpoint` override for tests.
## 9. Report
`docs/tasks/0689-report.md`: test tail, diff stat.
