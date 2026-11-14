# 1651 report: Go MarkFromWSUser

Status: review

## Files changed

- `go/internal/validation/ws_user.go` (created, 26 lines)
- `go/internal/validation/ws_user_test.go` (created, 29 lines)
- `go/internal/validation/testdata/ws_user_golden.json` (created, 114 lines)
- `docs/tasks/1651-report.md` (this file)

Diff against `go-demo-ports`: 3 files, +169 lines (the three code files above). The report is added in step 3.

## Checks (§4 step 0): all matched

`ws_user.go` absent; `wsUserRE` count 2; `func pyStrip` count 1; `def mark_from_ws_user` count 1; sidecar count 3.

## Commands (last 5 lines of output)

Step 1, sha256sum -c (whole output, 3 lines):
```
go/internal/validation/ws_user.go: OK
go/internal/validation/ws_user_test.go: OK
go/internal/validation/testdata/ws_user_golden.json: OK
```

Step 2, gofmt -l / go build ./... / go vet: no output from any of the three.

Step 2, go test ./internal/validation/ -count=1 -v | grep (3 lines):
```
=== RUN   TestMarkFromWSUserMatchesPython
--- PASS: TestMarkFromWSUserMatchesPython (0.00s)
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation	0.046s
```

Step 3, python3 scripts/context_lint.py (last 5 lines):
```
WARN  go/internal/web/auth/auth_test.go is named by open briefs 1282-go-auth-routes.md, 1505-go-auth-account-setup.md; say which goes first
WARN  test_0705_v2_shell_browser.py::test_non_v2_dashboard_still_loads_the_old_stylesheets_and_sidebar is named by open briefs 0784-settings-area-v2-old-shell-tests.md, 0851-fix-725-ci-and-savebar.md; say which goes first
WARN  test_signed_in_chrome.py::test_the_support_line_is_not_part_of_the_legal_link_row is named by open briefs 0784-settings-area-v2-old-shell-tests.md, 0851-fix-725-ci-and-savebar.md; say which goes first
next free: task 1653 | goose migration 00018 (App/app/migrations/ is frozen)
context lint: OK
```

## SKIP count

0 (validation package, `-v` run; no `--- SKIP` lines).

## Section 7 acceptance

- [x] `sha256sum -c` printed `: OK` for all 3 files.
- [x] Step 2 printed nothing before the final `ok` line.
- [x] Diff against the base lists only the §3 paths and the sidecars (see Files changed).

## Deviations

- The brief's §7 uses `git diff --stat main...HEAD`; there is no `main` in this worktree, so the diff was taken against `go-demo-ports`.
- The brief's executor section says to open one PR. Per the caller's instruction, no PR was opened and nothing was pushed.
- `go build ./...` downloaded the Go toolchain (go1.25.14) and modules on first run. It completed with no errors.

## Questions

None.

## Owner steps left

None (nothing uses the function yet). Review and merge are the owner's, with no push or PR from this run.
