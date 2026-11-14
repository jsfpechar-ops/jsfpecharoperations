# 1541 report: Go public property page and booking quote step

Status: review. One big PR mode: commits on the current branch (go-wave3), not pushed, no PR opened. The orchestrator collects the commits.

## Files changed (section 3 only)
- go/cmd/ubyhost-web/register_web_booking_property.go (new)
- go/internal/web/booking/pagectx.go (new)
- go/internal/web/booking/property.go (new)
- go/internal/web/booking/property_test.go (new)
- go/internal/web/booking/templates/book.tmpl (new)
- go/internal/web/booking/templates/property.tmpl (new)
- go/internal/web/booking/view.go (new)
- docs/tasks/1541-report.md (new), brief Status set to review

## Commands
- sha256sum -c (step 2): all 7 lines OK.
- go build ./... && go vet ./internal/web/booking/ ./cmd/ubyhost-web/ && gofmt -l internal/web cmd: no output.
- App/.venv/bin/python scripts/go_host_i18n.py --check: no output, exit 0.
- UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5610/postgres go test -count=1 ./internal/web/booking/ ./cmd/ubyhost-web/: ok, ok.
- Skipped tests in booking package: 0 (go test -v). cmd package: 0 skipped, 45 pass.

## Acceptance (section 7)
- [x] sha256 OK
- [x] step 1 commit lists only section 3 paths
- [x] both packages ok with database set
- [x] registerRoutes count in register_web_booking_property.go: 1
- [ ] Screenshots: deferred to 1550 (no served page changed here)

## Deviations
- Step 0 used `git reset --hard go-wave3` as instructed.
- Created App/.venv for the step 4 script (not committed).
- Started PostgreSQL 16 on port 5610, data dir /var/tmp/pg5610, as user postgres.

## Owner steps left
1. Before merging, check the server value of UBYHOST_GO_PATHS. If it contains `/p/*`, remove it until briefs 1542 and 1543 switch together (see brief 1550).
