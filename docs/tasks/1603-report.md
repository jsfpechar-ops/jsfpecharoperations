# 1603 report

Status: review

## Files changed

- `go/internal/web/onboarding/wizard_demo_delete.go` (new, from sidecar, sha256 verified)
- `go/internal/web/onboarding/wizard_post_test.go` (replaced from sidecar, sha256 verified; old 501 test removed)
- `go/internal/web/onboarding/wizard_post.go` (skip case calls `wizardDeleteDemoStay`; header comment updated)
- `docs/tasks/1603-files/**` (sidecars, copied into repo paths as the brief directs)
- `docs/tasks/1603-report.md` (this file)

## Commands (last 5 lines)

- `sha256sum` of both sidecar-backed files: both match the brief hashes (`db25e75f...`, `c1436cde...`).
- `gofmt -l internal/web/onboarding cmd/ubyhost-web && go build ./... && go vet ./internal/web/onboarding/... ./cmd/...`: no output.
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55603/postgres go test ./internal/web/onboarding/ ./cmd/ubyhost-web/ -count=1`:
  ```
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding	8.645s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.198s
  ```
- `go test -v -run '^(TestWizardSkipDeletesDemoStay|TestWizardSkipNeverDeletesARealStay|TestWizardSkipStopsWhenAPhotoStays|TestWizardAutomationTiming|TestWizardPostMatchesPython)$'`:
  ```
  --- PASS: TestWizardPostMatchesPython (0.67s)
  --- PASS: TestWizardSkipDeletesDemoStay (0.56s)
  --- PASS: TestWizardSkipNeverDeletesARealStay (0.55s)
  --- PASS: TestWizardSkipStopsWhenAPhotoStays (0.50s)
  --- PASS: TestWizardAutomationTiming (0.00s)
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding	2.310s
  ```
- Full verbose run of both packages: 0 `--- SKIP` lines.

## Acceptance (brief section 7)

- [x] sha256 of both sidecar files matches.
- [x] Step 3 printed nothing; step 5 `ok` for both packages, five `--- PASS` on PostgreSQL.
- [x] `TestWizardSkipWithDemoStayIs501` no longer exists.
- [x] Only the paths of section 3 and the sidecars changed.
- [x] No `UBYHOST_GO_PATHS`, compose, Caddy, env or Python change; nothing pushed.
- [x] UI: not applicable (no template or CSS change).

## Deviations

- PostgreSQL: started own PG16 on port 55603 (data `/var/tmp/pg1603/data`, socket dir `/var/tmp/pg1603`, UTF8) as instructed, not the brief's 55440.
- Step 2 edits were applied with the editor tool; the brief's exact anchors matched.
- Done: steps 1 to 6. Left: none.

## Questions

None.

## Owner steps left

1. Deploy brief 1640 first (writable data volume).
2. Brief 1604 owner steps route the wizard paths to Go. Then check "Delete and continue" on staging as in the brief.
3. Rollback: remove the two wizard paths from `UBYHOST_GO_PATHS` and run `docker compose up -d`.
