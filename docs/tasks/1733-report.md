# 1733 report: Go host guest add/edit

Status: review

## Commits

- `1733 step 1` — sidecars copied; MANIFEST sha256 all OK
- `1733 step 2` — `go_guest_edit_golden.py` run (golden unchanged)
- `1733 step 3` — gofmt (no diff)
- `1733 step 4` — dormant `register_web_stays_guest_edit.go`
- `1733 step 5` — acceptance commands and this report

## Commands (tail)

gofmt -l . — empty.

go test ./internal/web/stays/... ./cmd/ubyhost-web/... — ok both.

pytest tests/test_go_guest_edit_golden.py — 1 passed.

context_lint.py — OK.

Full go test ./internal/web/... needs UBYHOST_TEST_DATABASE_URL (settings package).

## Screenshots

Go paths dormant until 1737; UX gate at flip.

## Accepted differences

None in guest_edit_golden.json.

## §7

- [x] Dormant registration; no UBYHOST_GO_PATHS
- [x] Golden pytest green
- [x] diff vs main: §3 + report
- [x] steps 1–5 committed

## Deviations

None.

## Owner steps

None.
