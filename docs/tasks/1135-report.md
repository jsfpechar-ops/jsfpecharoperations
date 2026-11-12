# 1135 report: Go posthog job

Status: review

## 1. Diff stat (since brief commit)

```
 docs/ENVIRONMENT.md              |   2 +-
 go/cmd/ubyhost-web/main.go       |  10 +-
 go/internal/posthog/sync.go      | 415 +++++++++++++++++++++++++++++++++++++++
 go/internal/posthog/sync_test.go | 324 ++++++++++++++++++++++++++++++
 4 files changed, 749 insertions(+), 2 deletions(-)
```

## 2. Command results

- gofmt, go vet ./..., go test ./internal/posthog/ ./cmd/ubyhost-web/ -count=1: `ok` for both packages.
- Eight targeted tests: all `--- PASS` (EventUUID, ApiHost, ConfigFromEnv, StagesToSend, PersonSet, MonthStarts, CapturePayload, SyncOff).
- `go build` of ubyhost-web: exit 0.
- `python3 scripts/context_lint.py`: `context lint: OK`.
- `TestSyncEndToEnd`: skipped locally (no `UBYHOST_TEST_DATABASE_URL`); runs in CI.

## 3. Acceptance (section 7)

- [x] First §6 command prints two `ok` lines.
- [x] `go.mod`, `go.sum`, `App/` unchanged (diff prints nothing).
- [x] `grep -c '"posthog"' go/cmd/ubyhost-web/main.go` = 2.
- [x] No e-mail in slog lines in sync.go.
- [x] context_lint passes.
- [x] Only §3 paths changed (diff above).
- [x] Commits "1135 step 1" to "1135 step 5"; nothing pushed.

## 4. Deviations

None to code. Done: steps 0 to 5 (step 0 anchors all matched).

## 5. Questions

None.

## 6. Follow-up

Add a test-map row "Go module (`go/`)" in a later brief.

## 7. Owner steps left

Per brief "Owner steps": review and merge the PR via `scripts/merge-pr-on-green.sh`; switch only after a healthy deploy (add `posthog` to `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS` in `/opt/ubyhost/deploy/lightsail/.env`); then `docker compose up -d` from `/opt/ubyhost/deploy/lightsail`.
