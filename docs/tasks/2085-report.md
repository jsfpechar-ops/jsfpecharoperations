# 2085 Report: Use Prague civil date in Go stays overdue window, ordering, and range defaults

## 1. `git diff --stat` (code changes)

```
 go/internal/web/stays/handlers.go     |  2 +-
 go/internal/web/stays/overdue.go      |  2 +-
 go/internal/web/stays/overdue_test.go | 87 +++++++++++++++++++++++++++++++++++
 go/internal/web/stays/query.go        |  4 +-
 4 files changed, 92 insertions(+), 3 deletions(-)
```

## 2. §6 Commands

- `cd go && test -z "$(gofmt -l .)" && echo "gofmt OK"` — **PASS**

```
gofmt OK
```

- `cd go && go vet ./...` — **PASS** (exit 0, no output)

- `cd go && go test ./internal/web/stays/... -count=1 -v` — **PASS** (`TestOverdueUnfinishedIDsPragueDateNearMidnight` ran and passed in 0.16s, 0 skipped)

```
=== RUN   TestStaysListVisibleTextNoRawI18nKeys
--- PASS: TestStaysListVisibleTextNoRawI18nKeys (0.01s)
=== CONT  TestSourceLabelMatchesPython
--- PASS: TestSourceLabelMatchesPython (0.00s)
PASS
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays	2.224s
```

- `cd go && go test ./... -count=1` — **PASS**

```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees	7.715s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays	3.396s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/submissions	0.780s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/webpush	0.011s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/welcomeback	0.004s
```

- `python3 scripts/context_lint.py` — **PASS**

```
WARN  3 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 2086 | goose migration 00025 (App/app/migrations/ is frozen)
context lint: OK
```

## 3. §7 Acceptance

- [x] `go/internal/web/stays/overdue.go` computes `today := civilDate(deadlines.LocalNow(at))`.
- [x] `go/internal/web/stays/query.go` computes `todayISO := formatISODate(civilDate(deadlines.LocalNow(at)))`.
- [x] `go/internal/web/stays/handlers.go` passes `pragueToday(at)` to `ParseParams`.
- [x] `TestOverdueUnfinishedIDsPragueDateNearMidnight` runs and passes (not skipped), proving `2026-10-10` is excluded, `2026-10-11` is included, `upcoming` starts on `2026-11-25`, and `List` ranks `2026-11-25..2026-11-26` ahead of `2026-11-24..2026-11-24` at `2026-11-24T23:30:00Z`.
- [x] `gofmt -l .` is empty, `go vet ./...` exits 0, `go test ./internal/web/stays/... -count=1 -v` passes, and `python3 scripts/context_lint.py` reports `context lint: OK`.

## 4. Deviations

None (also ran full `go test ./... -count=1` as requested by the orchestrator prompt; all packages passed).

## 5. Questions

None.

## 6. Owner steps left

1. None (internal Go parity bugfix; re-run `scripts/e2e/parity_gate.sh` in CI or before cutover).
