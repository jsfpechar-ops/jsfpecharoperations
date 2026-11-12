# 1133: Repoint the Go deadline copies in ubyport and calendar to `deadlines`

Status: review
Depends on: 1132 (merged) | Base commit: main d353dec | Branch: the orchestrator's branch (work on the current branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`go/internal/ubyport/collect.go` and `go/internal/calendar/progress.go` each carry their own copy of the three-working-day deadline. This brief makes both call the parity-checked package `go/internal/deadlines` (brief 1132) and deletes the copies, so there is one Go deadline and it is the one the Python golden file checks. It is slice A of brief 1132 §10. **Behaviour-neutral:** every caller gets exactly the value it gets today (proof in §2).

This is a refactor, not a fix: there is no failing-first step. The existing tests must stay green unchanged in meaning.

## 2. Context

Rules: AGENTS.md hard rule 1 (filing correctness beats everything: `ubyport.ReportingDeadline` caps the automatic send in `DueForAutomaticSend`), rule 4 (no new dependency: only the in-module package `internal/deadlines`; no `go.mod` change). No SQL, no env var, no `App/` change. `go/internal/deadlines` stays a leaf: it imports only the stdlib and this brief does not touch it.

**Every caller of the removed or changed symbols** (grep of `go/`, tests included, at d353dec):

| Symbol | Callers | Decision |
|---|---|---|
| `ubyport.ReportingDeadline` (exported, Prague-zoned) | `ubyport/collect.go` 348 (`DueForAutomaticSend`), `ubyport/collect_test.go` 287 (`TestReportingDeadline`), `calendar/progress.go` 34 | **kept** as a thin wrapper over `deadlines.ReportingDeadline` that returns the same Prague-zoned `time.Time`. Keeping it changes 0 caller files; repointing would touch `DueForAutomaticSend` (filing path) and its test for no gain. |
| `ubyport.addWorkingDays`, `isWorkingDay`, `reportingWorkingDays` (unexported) | only `ReportingDeadline` | deleted |
| `calendar.localNow` | `calendar/handler.go` 207, `calendar/progress.go` 218 | **kept** as a one-line wrapper (see difference 1); `handler.go` does not change |
| `calendar.reportingDeadlineNaive` | `calendar/progress.go` 212, `calendar/calendar_test.go` 115 | deleted; callers use `deadlines.ReportingDeadline` |
| `calendar.urgency` | `calendar/progress.go` 211, `calendar/calendar_test.go` 128 | deleted; callers use `deadlines.Urgency` |
| `calendar.prague`, `mustLoadPrague`, `naive` | only the functions above | deleted (`ical` has its own `prague`; other packages are unaffected) |

`pragueZone` (defined in `ubyport/notify.go` 48) and `import _ "time/tzdata"` in `collect.go` stay: the wrapper still loads the zone. `progress.go` keeps its `ubyport` import (`ubyport.ParseStoredUTC`, line 192). `calendar` never imported `time/tzdata` itself; `deadlines` does.

**Line-by-line comparison, old vs new:**

- Check-in day: old `ubyport.ReportingDeadline` takes `checkIn.Year/Month/Day()` in the value's own zone; `deadlines.dateOnly` uses `checkIn.Date()`, the same fields. Time of day of the input is ignored by both.
- Working days: both count Monday to Friday, no holidays; a working start day is day one, a weekend start opens on the next working day (Sat 31 Oct and Sun 1 Nov 2026 both give Wed 4 Nov; Fri 30 Oct gives Tue 3 Nov).
- Result: old returns `time.Date(y,m,d,23,59,59,0,Prague)`. The wrapper takes the naive wall clock of `deadlines.ReportingDeadline` (always 23:59:59, UTC-labelled) and rebuilds `time.Date(y,m,d,h,mi,s,0,Prague)`: identical instant **and** identical zone. DST: the deadline day's own offset is applied by `time.Date` in both (22 Oct 2026 check-in gives Mon 26 Oct 22:59:59Z, CET, after the 25 Oct change; June gives 21:59:59Z, CEST). `TestReportingDeadline` covers these and step 3 adds a zone check.
- `calendar.reportingDeadlineNaive` = `naive(ubyport.ReportingDeadline(c))` = 23:59:59 UTC-labelled on the same day = `deadlines.ReportingDeadline(c)`.
- `calendar.urgency` vs `deadlines.Urgency`: same thresholds (`< 0` overdue, `<= 24` urgent, `<= 48` soon, else ok). Old uses `Duration.Hours()`, new `Seconds()/3600`; for whole-second inputs the true value is either exactly 0/24/48 or at least 1/3600 h away, so both land on the same side of every threshold.

**Behaviour differences found (all preserved by this diff):**

1. **Sub-second digits.** Old `calendar.localNow` drops nanoseconds (`naive` builds with `0` ns); `deadlines.LocalNow` keeps them. `localNow` converts stored filing times (`ParseStoredUTC` accepts `.999999999`) into `filedAt`, compared with the 23:59:59 deadline in `deadlineCell`. Without truncation a filing stored at 23:59:59.5 Prague would turn "filed late" (min 1 h). **Preserved:** `localNow` stays and returns `deadlines.LocalNow(now).Truncate(time.Second)` (same UTC-labelled value, whole seconds). Step 2 adds `TestLocalNowDropsSubSeconds`. Because `now` stays whole-second, the `Hours()` vs `Seconds()/3600` point above holds.
2. **Check-in with a clock or zone (latent, unreachable).** Old `urgency` compared `checkIn.After(today)` raw; `deadlines.Urgency` compares `dateOnly(checkIn)`. They differ only if `checkIn` is not UTC midnight. The only producer is `anchorDate` → `validation.ParseISODate` → `roundTrip`, which always returns `time.Date(y,m,d,0,0,0,0,time.UTC)`, so no caller can see it. Not changed by design; listed so a reviewer does not have to rediscover it.

The brief writer applied these exact edits to a scratch copy at d353dec: `gofmt -l` empty, `go vet ./...` clean, `go test ./internal/deadlines/ ./internal/ubyport/ ./internal/calendar/` ok, `go build ./cmd/ubyhost-web` ok, and a throwaway comparison of old vs new over every check-in day 2024-2030 (four input zones, four input hours) and ~17.7 million `now` values (every 30 min ±1 s over ±6 days, with 0/1/500 ms/999 ms nanoseconds, plus exact 0/24/48 h thresholds) found zero differences in `ReportingDeadline` (instant, zone, `String()`), `localNow` and urgency.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/ubyport/collect.go` | edit | import `deadlines`; `ReportingDeadline` becomes a wrapper; delete `reportingWorkingDays`, `addWorkingDays`, `isWorkingDay` |
| `go/internal/calendar/progress.go` | edit | import `deadlines`; delete `prague`, `mustLoadPrague`, `naive`, `reportingDeadlineNaive`, `urgency`; `localNow` becomes a wrapper; `stayCell` calls `deadlines` |
| `go/internal/calendar/calendar_test.go` | edit | `TestUrgencyBuckets` uses the `deadlines` names; add `TestLocalNowDropsSubSeconds` |
| `go/internal/ubyport/collect_test.go` | edit | `TestReportingDeadline` also checks the zone is Europe/Prague |
| `docs/tasks/1133-go-deadlines-repoint.md` | edit | `Status:` line only (step 4) |
| `docs/tasks/1133-report.md` | create | the report (§9) |

No other file may change. `go/internal/deadlines/` is not touched.

## 4. Steps

Work on the branch you are on. Do not create a branch, do not push, do not open a PR. After each step run its command, then `git add <that step's files> && git commit -m "1133 step k"`, nothing else staged. Paste every block byte for byte with the Edit tool: Go indentation is **tabs**. "Replace" means the old block must match exactly once; if it does not, STOP (§8).

0. Anchor check, from the repo root:
   `grep -cF 'func addWorkingDays(start time.Time, count int) time.Time {' go/internal/ubyport/collect.go; grep -cF 'func reportingDeadlineNaive(checkIn time.Time) time.Time {' go/internal/calendar/progress.go; grep -cF 'deadline := reportingDeadlineNaive(checkIn)' go/internal/calendar/calendar_test.go; grep -cF 'if got := ReportingDeadline(in).UTC().Format(time.RFC3339); got != c.want {' go/internal/ubyport/collect_test.go; grep -c 'internal/ubyport\|internal/calendar' go/internal/deadlines/deadlines.go; ls docs/tasks/1133-report.md 2>&1 | tail -30`
   Expected: `1`, `1`, `1`, `1`, `0`, then "No such file or directory". Anything else: STOP.

1. `go/internal/ubyport/collect.go`.

   a. In the import block, replace

```go
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)
```

   with

```go
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)
```

   b. Replace this whole block (33 lines, from the `ReportingDeadline` comment to the closing `}` of `isWorkingDay`):

```go
// ReportingDeadline is deadlines.reporting_deadline: 23:59:59 Prague wall time on
// the third working day of the window that opens on checkIn (its Y/M/D are used).
func ReportingDeadline(checkIn time.Time) time.Time {
	loc, err := time.LoadLocation(pragueZone)
	if err != nil {
		panic("collect: embedded Prague zone missing: " + err.Error())
	}
	start := time.Date(checkIn.Year(), checkIn.Month(), checkIn.Day(), 0, 0, 0, 0, time.UTC)
	day := addWorkingDays(start, reportingWorkingDays)
	return time.Date(day.Year(), day.Month(), day.Day(), 23, 59, 59, 0, loc)
}

const reportingWorkingDays = 3 // deadlines.REPORTING_WORKING_DAYS

// addWorkingDays is deadlines.add_working_days: Monday to Friday; holidays count.
func addWorkingDays(start time.Time, count int) time.Time {
	current := start
	remaining := count
	if isWorkingDay(current) {
		remaining = count - 1
	}
	for remaining > 0 {
		current = current.AddDate(0, 0, 1)
		if isWorkingDay(current) {
			remaining--
		}
	}
	return current
}

func isWorkingDay(d time.Time) bool {
	return d.Weekday() != time.Saturday && d.Weekday() != time.Sunday
}
```

   with

```go
// ReportingDeadline is deadlines.reporting_deadline as a real instant: the
// naive wall clock of deadlines.ReportingDeadline (23:59:59 on the third
// working day of the window that opens on checkIn, its Y/M/D are used) read
// in Europe/Prague. The returned time is in the Prague zone.
func ReportingDeadline(checkIn time.Time) time.Time {
	loc, err := time.LoadLocation(pragueZone)
	if err != nil {
		panic("collect: embedded Prague zone missing: " + err.Error())
	}
	d := deadlines.ReportingDeadline(checkIn)
	return time.Date(d.Year(), d.Month(), d.Day(), d.Hour(), d.Minute(), d.Second(), 0, loc)
}
```

   Command, from `go/`: `test -z "$(gofmt -l .)" && go build ./... && go test ./internal/ubyport/ -run 'TestReportingDeadline|TestDueForAutomaticSend' -count=1 2>&1 | tail -30`. Expected: `ok`. Commit "1133 step 1" (`go/internal/ubyport/collect.go`).

2. `go/internal/calendar/progress.go` and `go/internal/calendar/calendar_test.go` (one step: the test uses the deleted names, so they change together).

   a. `progress.go`, in the import block, replace

```go
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
```

   with

```go
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
```

   b. `progress.go`, replace this whole block (from the `prague` comment to the closing `}` of `urgency`):

```go
// prague is the Europe/Prague zone the deadlines use for civil time.
var prague = mustLoadPrague()

func mustLoadPrague() *time.Location {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		panic("calendar: embedded Prague zone missing: " + err.Error())
	}
	return loc
}

// naive keeps the wall clock of t and drops its zone (a Python naive datetime).
func naive(t time.Time) time.Time {
	return time.Date(t.Year(), t.Month(), t.Day(), t.Hour(), t.Minute(), t.Second(), 0, time.UTC)
}

// localNow is deadlines.local_now for an instant: the naive Prague wall clock.
func localNow(now time.Time) time.Time {
	return naive(now.In(prague))
}

// reportingDeadlineNaive is deadlines.reporting_deadline as a naive datetime.
func reportingDeadlineNaive(checkIn time.Time) time.Time {
	return naive(ubyport.ReportingDeadline(checkIn))
}

// urgency mirrors deadlines.urgency. checkIn is a date (UTC midnight); now is naive Prague time.
func urgency(checkIn, now time.Time) string {
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	if checkIn.After(today) {
		return "future"
	}
	left := reportingDeadlineNaive(checkIn).Sub(now).Hours()
	switch {
	case left < 0:
		return "overdue"
	case left <= 24:
		return "urgent"
	case left <= 48:
		return "soon"
	}
	return "ok"
}
```

   with

```go
// localNow is deadlines.LocalNow cut to whole seconds: the naive Prague wall
// clock. The calendar has always dropped sub-second digits (a stored filing
// time may carry microseconds); keep that so a filing at 23:59:59.5 is not late.
func localNow(now time.Time) time.Time {
	return deadlines.LocalNow(now).Truncate(time.Second)
}
```

   c. `progress.go`, in `stayCell`, replace

```go
		level = urgency(checkIn, now)
		d := reportingDeadlineNaive(checkIn)
```

   with

```go
		level = deadlines.Urgency(checkIn, now)
		d := deadlines.ReportingDeadline(checkIn)
```

   d. `calendar_test.go`, in the import block, replace

```go
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)
```

   with

```go
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)
```

   e. `calendar_test.go`, replace

```go
	deadline := reportingDeadlineNaive(checkIn)
```

   with

```go
	deadline := deadlines.ReportingDeadline(checkIn)
```

   f. `calendar_test.go`, at the end of `TestUrgencyBuckets`, replace

```go
		if got := urgency(checkIn, c.now); got != c.want {
			t.Errorf("%s: got %q want %q", c.name, got, c.want)
		}
	}
}
```

   with

```go
		if got := deadlines.Urgency(checkIn, c.now); got != c.want {
			t.Errorf("%s: got %q want %q", c.name, got, c.want)
		}
	}
}

// localNow keeps the calendar's old whole-second wall clock (brief 1133): a
// filing stored at 22:59:59.5 UTC on a winter deadline day is 23:59:59 Prague,
// on time, not half a second late.
func TestLocalNowDropsSubSeconds(t *testing.T) {
	got := localNow(time.Date(2026, 11, 4, 22, 59, 59, 500000000, time.UTC))
	if want := time.Date(2026, 11, 4, 23, 59, 59, 0, time.UTC); !got.Equal(want) || got.Location() != time.UTC {
		t.Errorf("got %v, want %v", got, want)
	}
	due := deadlines.ReportingDeadline(time.Date(2026, 11, 2, 0, 0, 0, 0, time.UTC))
	if got.After(due) {
		t.Errorf("filed %v is after the deadline %v", got, due)
	}
}
```

   Command, from `go/`: `test -z "$(gofmt -l .)" && go vet ./internal/calendar/ && go test ./internal/calendar/ -count=1 2>&1 | tail -30`. Expected: `ok`. Then `grep -nE 'func (naive|urgency|reportingDeadlineNaive|mustLoadPrague)\b|var prague' internal/calendar/*.go | tail -30` prints nothing. Commit "1133 step 2" (both files).

3. `go/internal/ubyport/collect_test.go`, in `TestReportingDeadline`, replace

```go
		if got := ReportingDeadline(in).UTC().Format(time.RFC3339); got != c.want {
			t.Errorf("check-in %s: deadline %s, want %s", c.checkIn, got, c.want)
		}
```

   with

```go
		if got := ReportingDeadline(in).UTC().Format(time.RFC3339); got != c.want {
			t.Errorf("check-in %s: deadline %s, want %s", c.checkIn, got, c.want)
		}
		if zone := ReportingDeadline(in).Location().String(); zone != "Europe/Prague" {
			t.Errorf("check-in %s: deadline zone %s, want Europe/Prague", c.checkIn, zone)
		}
```

   Command: the §6 Go command. Expected: three `ok` lines, then the build prints nothing. Commit "1133 step 3".

4. Run every §6 command, write `docs/tasks/1133-report.md` (§9), change this brief's `Status: todo` line to `Status: review`, then `git add docs/tasks/1133-report.md docs/tasks/1133-go-deadlines-repoint.md && git commit -m "1133 step 4"`.

## 5. Do not touch

`go/internal/deadlines/` (all of it, including `testdata/golden.json`), `go/internal/calendar/handler.go`, `go/internal/ubyport/notify.go`, every other Go file, `go/go.mod`, `go/go.sum`, `go/Dockerfile`, `App/` (all of it), `.github/`, `docs/context/`, every file not in §3. Do not "tidy" the old header comment of `collect.go` or anything outside the blocks above. Hard rules 1, 3, 4, 5, 8. No new dependency, no SQL, no env var, no push.

## 6. Commands

From `go/` (the CI step "Format, vet, test and build the Go module", narrowed to the three packages; CI runs `go test ./...`):

```bash
test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/deadlines/ ./internal/ubyport/ ./internal/calendar/ -count=1 2>&1 | tail -30
```

Expected: three `ok` lines (log lines from `ubyport` tests are normal; tests that need `UBYHOST_TEST_DATABASE_URL` skip locally and run in CI).

```bash
go build ./cmd/ubyhost-web 2>&1 | tail -30 && rm -f ubyhost-web
```

Expected: no output.

From the repo root:

```bash
python3 scripts/context_lint.py 2>&1 | tail -30
```

Expected: passes.

[Test-map](../context/test-map.md): it has no Go row; the "Filing, UbyPort, claim" row lists Python tests for `App/` files. This brief changes no `App/` file, so no Python test is run; the Go commands above are the check (the brief 1132 golden test already pins `deadlines` to the Python).

## 7. Acceptance

- [ ] From `go/`: the first §6 command prints three `ok` lines; `go build ./cmd/ubyhost-web` succeeds.
- [ ] `grep -rnE 'func (addWorkingDays|isWorkingDay|naive|urgency|reportingDeadlineNaive|mustLoadPrague)\b|reportingWorkingDays' go/internal/ubyport go/internal/calendar | tail -30` prints nothing.
- [ ] `grep -rn 'internal/ubyport\|internal/calendar' go/internal/deadlines | tail -30` prints nothing (still a leaf).
- [ ] `TestReportingDeadline` (with the zone check), `TestDueForAutomaticSendDeadlineCap`, `TestUrgencyBuckets` and `TestLocalNowDropsSubSeconds` pass (`go test ./internal/ubyport/ ./internal/calendar/ -run 'TestReportingDeadline|TestDueForAutomaticSend|TestUrgencyBuckets|TestLocalNowDropsSubSeconds' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`).
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat "$(git log -1 --format=%H --grep=^Brief.1133)"..HEAD | tail -30` lists only the §3 paths.
- [ ] Four commits "1133 step 1" to "1133 step 4"; nothing pushed.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in step 0 gives another count, or a "replace" block is not found exactly once;
- a test fails twice, or any existing test needs its expected value changed (that would be a behaviour change: never edit a `want` to make it pass);
- `go vet` reports an unused import or symbol you cannot fix inside the §3 blocks;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed, or `go.mod`/`go.sum` changes;
- a file outside §3 needs a change (for example `handler.go`);
- a step is unclear;
- you need push, merge, a PR, secrets, SSH or deploy (the orchestrator or owner does that).

## 9. Report

Write `docs/tasks/1133-report.md` (600 tokens at most) with: 1. `git diff --stat "$(git log -1 --format=%H --grep=^Brief.1133)"..HEAD` (last 10 lines); 2. each §6 command with the last 5 lines of its output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left (expected: none beyond the PR review).

## Risk list (for the reviewer)

Read the full diff of all four Go files. Focus: `ubyport.ReportingDeadline` returns the same instant **and** the Prague zone (it caps `DueForAutomaticSend`, the automatic filing time); `calendar.localNow` still truncates to whole seconds; no `want` value in any test changed; `go/internal/deadlines` is untouched.

## Owner steps

1. Review the draft PR when the orchestrator says it is green; merge it with `scripts/merge-pr-on-green.sh` as usual. Nothing to deploy or configure: no env var, no migration.
