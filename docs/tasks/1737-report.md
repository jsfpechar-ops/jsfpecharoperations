# 1737 report

Status: review

## Commits

- `1737 step 1` — `register_web_stays_all_test.go`, wave H in go-cutover-runbook.md
- `1737 step 5` — this report

## Commands

- `go test ./cmd/ubyhost-web/... -run TestStaysAllRoutesRegistered` — ok
- `go test ./internal/web/stays/... ./cmd/ubyhost-web/...` — ok

## Deviations

- Branch includes unmerged 1735 commits; rebase onto `main` after 1735 PR merges.
- Steps 2–4 in brief N/A (no golden/handlers in §3; only completeness test + runbook).

## §7

- [x] TestStaysAllRoutesRegistered passes with 1730–1735 registers on branch tip

## Questions

None.