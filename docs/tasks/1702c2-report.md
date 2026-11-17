# 1702c2 report

Status: review

## Files changed (`git show --stat`, steps 1 and 7)
- go/internal/web/properties/apartment_update.go
- go/internal/web/properties/apartment_update_test.go
- go/internal/web/properties/apartment_create.go
- go/internal/web/properties/apartment_detail.go
- docs/tasks/1702c2-report.md
- docs/tasks/1702c2-go-apartment-save-refused-page.md

## Commands (last 5 lines)
- Step 0 hash check: four `: OK` lines; branch, 1702c1 step 7 commit `1`, sidecar count `4`.
- Step 1 sidecar copy and hash check: four `: OK`.
- Step 2 gofmt, build, vet: no output, rc=0.
- Step 3 Python checks: CI only (no App/.venv).
- Step 4 PostgreSQL 16: started at /var/tmp/pg55493 on port 55493, stopped and removed afterwards.
- Step 5 `go test` (properties, palette, ubyhost-web): `ok` x3; eleven named tests `--- PASS`; SKIP count `0`.
- Lint: `context lint: OK`.

## Section 7
- [x] Step 0: `1`, `4`, four `: OK`; step 1: four `: OK`.
- [x] Step 2 printed nothing.
- [x] Step 3: CI only (no App/.venv).
- [x] Step 5: three `ok`, eleven named tests PASS, SKIP count 0.
- [x] Nothing in App/ changed.

## Deviations
- Step 4: the scratchpad path was not accessible to the postgres user, so the cluster used the brief's /var/tmp/pg55493 path (port 55493).
- Step 3 skipped: no App/.venv, so the Python golden checks are left to CI.

## Accepted differences (from brief §2)
- `door_switch_posted` not ported (read by no template).
- `account` of `refuse_fee_save` not ported (read by no Go or Python property template).
- Wizard branches stay with Python (1702c1).

UX pending until 1705 (no template change; 400 screenshots taken there). 1702d is next.
