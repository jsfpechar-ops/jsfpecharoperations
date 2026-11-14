# 1570 report: Go cleaning host pages, part 1

Status: review. One big PR mode: commits on the local branch (worktree-agent-a73c92cb05d43c52a, reset to go-wave3). Nothing pushed, no PR opened.

## 1. Files changed

- Created (9, copied from sidecars, sha256 all OK): `go/cmd/ubyhost-web/register_web_cleaning_host.go`, `go/cmd/ubyhost-web/register_web_cleaning_host_test.go`, `go/internal/web/cleaning/host.go`, `go/internal/web/cleaning/host_data.go`, `go/internal/web/cleaning/host_test.go`, `go/internal/web/cleaning/hosttemplates/_calendar.tmpl`, `cleaning.tmpl`, `cleaning_edit.tmpl`, `cleaning_properties.tmpl`.
- Edited: `go/cmd/ubyhost-web/register_web_cleaning_test.go` (3 deletions).
- This report and the brief status line.

## 2. Commands

- Step 0 anchors: all as stated (12 greps = 1; `host.go` absent; 9 sidecars).
- Step 1 sha256sum: all 9 `: OK`.
- Step 3 gofmt, build, vet: no output.
- Step 5 tests on PostgreSQL 16, port 5634: `ok ... internal/web/cleaning 10.512s`, `ok ... cmd/ubyhost-web 0.134s`.
- Named tests: 9 of 9 `--- PASS`. SKIP lines: 0 (also 0 across both packages with `-v`).
- `context_lint.py`: FAIL, only because `1570-report.md` did not exist when the brief status was set to review (now written; rerun needed).

## 3. Acceptance

All ticked except the UI item, which is not applicable (dormant pages, rule 10 runs on staging per the brief).

## 4. Deviations

- PostgreSQL used port 5634 and `/var/tmp/pg5634` (task message), not the brief's 55570. Stopped after tests; directory left for cleanup.
- Branch name differs from the brief's `Branch:` line (one big PR mode).

## 5. Questions

None.

## 6. Owner steps left

None in this brief. Brief 1573 holds the path switch.
