# 1652 report

Status: review

## Files changed
- go/internal/web/booking/publish.go (new, sidecar copy, sha OK)
- go/internal/web/booking/publish_test.go (new, sha OK)
- go/internal/web/booking/testdata/slug_golden.json (new, sha OK)
- docs/tasks/1652-report.md (this file)

## Commands (last 5 lines of output)

Step 0 checks: all matched (publish.go absent; no existing Slug/Publish funcs; StampAt=1; x/text=1; Python def=1; sidecars=3).

Step 1 (sha256sum -c):
```
go/internal/web/booking/publish.go: OK
go/internal/web/booking/publish_test.go: OK
go/internal/web/booking/testdata/slug_golden.json: OK
```

Step 2 (gofmt -l / go build / go vet / go mod tidy -diff):
- gofmt: no output. vet: no output. tidy -diff: no output.
- build: only `go: downloading ...` module lines (filtered with grep -v downloading); exit 0.

Step 3: PostgreSQL 16 started on 127.0.0.1:55503 (data /var/tmp/pg1652/data), pg_isready: accepting connections.

Step 4a (go test ./internal/web/booking/ -count=1):
```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking	11.350s
```

Step 4b (-run TestSlugForMatchesPython|TestPublishPage -v):
```
--- PASS: TestSlugForMatchesPython (0.00s)
--- PASS: TestPublishPage (0.31s)
PASS
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking	0.317s
```

Full package -v: 41 PASS, 0 SKIP, 0 FAIL.

Step 5 (python3 scripts/context_lint.py): last lines
```
next free: task 1653 | goose migration 00018 (App/app/migrations/ is frozen)
context lint: OK
```
(WARN lines are pre-existing "named by open briefs" notices, not caused by this change.)

## SKIP count
0 (full package run, verbose).

## 7. Acceptance
- [x] sha256sum OK for all 3 files; step 2 printed nothing (apart from module download notices).
- [x] Step 4: ok for the package, two PASS, no SKIP.
- [ ] `git diff --stat main...HEAD` not run in this session (the diff is only the three go/ files plus this report).

## Deviations
- PostgreSQL port 55503 (launcher instruction) instead of brief's 55440.
- PostgreSQL started as user `nobody` (initdb/pg_ctl refuse root).
- Step 2 build output contains `go: downloading` module notices; no compile errors.
- Launcher said no PR and no push: no PR opened, nothing pushed.
- Step 0 "FIRST command" was preceded by a read-only `git status` (tree was clean) before the reset.

## Questions
- None.

## Owner steps left
- Coordinator adds the `go/internal/web/booking` test-map row (per brief).
- Review and PR by the owner or orchestrator.
