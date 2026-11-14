# 1521 report: Go port of "Sync now" (POST /sync)

Status: review. Branch: go-wave3 (one big PR mode, no push, no PR).

## Files changed (step 3 commit 876747632)
- create: go/internal/ical/syncowner.go, go/internal/web/properties/flashes.go, sync.go, sync_test.go, go/cmd/ubyhost-web/register_web_properties_sync.go
- edit: go/internal/web/properties/i18n_keys.txt (append), i18n.json (generated)
- edit (step 4): docs/tasks/1521-go-properties-sync.md Status line only

## Checks
- sha256 of the 5 sidecar files: 5 OK. i18n.json sha256 a34501e5785a460a5e2262a812dd815056cf56c6d3dee154be189b2ae6b0db97 (matches).
- gofmt -l: empty. go build ./...: clean. go vet (ical, properties, cmd): clean.
- go test -run 'Plural|SyncNow|SyncOwner' properties: TestPluralFlashKey PASS, TestSyncNow PASS.
- go test properties, ical, cmd/ubyhost-web: all ok (properties 16.7 s, ical 45.8 s). Skips: 0 (PostgreSQL 16 on port 5616, database ubyhost_test).
- Tests use only an httptest local server; no real calendar feed is fetched.
- python3 scripts/context_lint.py: OK.

## Deviations
- App/.venv created (requirements.txt and requirements-dev.txt), needed to run the catalog generator. It is not committed.
- Step 3 commit message follows the brief; the sidecar files are included in it.

## Questions
- None.

## Owner steps
1. Nothing to deploy yet. /sync can go into UBYHOST_GO_PATHS on its own.
2. On staging, press Sync now on / and compare the flash with Python.
