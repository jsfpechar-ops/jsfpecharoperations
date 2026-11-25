# 2084: PR 1319, merge origin/main and close the Go and Python CI reds

Status: review

## Files changed

```
go/internal/web/guest/form_save.go
go/internal/web/guest/form_save_test.go
go/internal/headcount/apply_declared_in.go (deleted)
go/internal/hostweb/layout/testdata/v2_cs_impersonating.html
go/internal/hostweb/layout/testdata/v2_alerts_hidden.html
go/internal/hostweb/layout/shell.html
App/app/templates/base.html
App/tests/static_versions.json
```

## Commands and results

### Step 1: Merge
```
$ git merge --no-ff origin/main
Auto-merging go/internal/web/guest/form_save.go
CONFLICT (content): Merge conflict in go/internal/web/guest/form_save.go
Auto-merging go/internal/web/guest/form_save_test.go
Automatic merge failed; fix conflicts and then commit the result.
```
Result: Exactly one conflict in form_save.go as expected.

### Step 3-7: Extract validation, delete dead code, format
Applied validation extraction into `guestSaveValidateIssues` function. Deleted `apply_declared_in.go`. Fixed formatting with gofmt.

### Step 8: Key bump to 20261124-2046a
Changed in 4 files and regenerated static_versions.json:
```
$ .venv/bin/python tests/test_static_versions.py --write
wrote /tmp/wt-2084/App/tests/static_versions.json (51 files)
```

### Step 6: Command tests

#### Go tests (guest, headcount, hostweb)
```
ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest       4.788s
ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount       0.003s
ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb         0.036s
ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout  0.202s
```

#### Full Go test suite
```
(no FAIL in output, all pass)
```

#### Guest save tests
```
--- PASS: TestGuestSaveNoticeAndHeadcount (0.17s)
--- PASS: TestGuestSaveValidateIssuesLegalAckOnEdit (0.00s)
--- PASS: TestGuestSaveValidateIssuesPartySizeOnNew (0.00s)
ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest       0.204s
```

#### Python tests
```
16 passed in 2.86s
```

#### Context lint
```
context lint: OK
(warnings are pre-existing brief conflicts)
```

## Acceptance (§7)

- [x] Merge commit with two parents (HEAD has 3 objects when counting `git rev-list --parents -n1 HEAD`)
- [x] No conflict markers; `git status --short` shows only staged changes
- [x] `gofmt -l .` and `go vet ./...` print nothing
- [x] Full `go test ./... -count=1` has no FAIL
- [x] All 2071 tests pass un-skipped: `TestGuestSaveNoticeAndHeadcount` (0.17s), and both `TestGuestSaveValidateIssues*` tests pass
- [x] `grep -rn '20261122-access-2036a' App go` prints nothing
- [x] `test_static_versions.py` and `test_wp07_cache_heartbeats.py` pass (16 passed)

## Deviations

None.

## Questions

None.

## Owner steps

None - orchestrator handles push and merge.
