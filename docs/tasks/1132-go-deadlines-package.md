# 1132: Go package `deadlines`, a parity-checked port of App/app/deadlines.py

Status: todo
Depends on: none | Base commit: main 90231ec4 | Branch: claude/fervent-cray-1qsrfa
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the pure Go package `go/internal/deadlines`, a line-for-line port of `App/app/deadlines.py`, and a golden file written by the real Python so that Go and Python cannot drift. Nothing calls the package yet: no job kind, no env var, no route, no migration, no SQL. It is slice 1 of moving the Python `deadlines` job to Go (§10 lists the rest).

This is not a fix brief: it adds new files and changes no existing file, so there is no failing-first step.

## 2. Context

Rules that apply: AGENTS.md hard rule 1 (filing correctness: **`App/app/deadlines.py` is the reference; Go must match its golden output exactly, hours-left floats included**), rule 4 (stdlib only: the Go code imports `fmt`, `math`, `time`, `time/tzdata`, the test `encoding/json`, `embed`, `testing`, `time`; the Python files only the stdlib and `app.deadlines`), rule 5 (no SQL here).

Go module (`go/go.mod`): `github.com/jsfpechar-ops/jsfpecharoperations/go`. The package is `.../go/internal/deadlines`. Existing small packages (`validation`, `secure`) have a package doc comment, stdlib `testing` only, and tests in the same package. Follow that.

CI step "Format, vet, test and build the Go module" (`working-directory: go`): `test -z "$(gofmt -l .)"`, `go vet ./...`, `go test ./... -count=1`, `go build ./cmd/ubyhost-web`. The Go code below is already gofmt-formatted (tabs). Paste it byte for byte; do not retype or re-align.

**What the Python does (read from `App/app/deadlines.py`, 116 lines):** `REPORTING_WORKING_DAYS = 3`; `is_working_day` is `day.weekday() < 5` (weekends only, **no Czech holiday list**, owner decision 2026-10-31); `add_working_days` counts the start day as day one when it is a working day, a weekend start opens the count on the next working day; `reporting_deadline` is 23:59:59 of the third working day as a **naive** datetime; `local_now` converts an aware datetime to naive Europe/Prague wall clock and returns a naive one unchanged; `hours_left`, `urgency`, `time_left_parts` work on naive wall-clock differences (so across a DST change day the difference is the wall-clock one, not the elapsed one; Go copies this by using UTC-labelled naive times); `describe_time_left` builds English text.

**Decisions in this brief:**

- `describe_time_left` IS ported (`DescribeTimeLeft`). It is pure and the Python app writes it into logs and stored alert text (`reporting.py` line 2714), so the later Go job must produce identical bytes. Templates use `time_left_parts` (host copy lives in the UI strings), and that is ported too.
- Go already has two partial copies: `ubyport.ReportingDeadline`, `addWorkingDays`, `isWorkingDay` (`go/internal/ubyport/collect.go` ~361-393, returns a Prague-zoned time) and `calendar.localNow`, `reportingDeadlineNaive`, `urgency` (`go/internal/calendar/progress.go` lines 11-52). This brief does **not** touch them: both packages are live, the new package must stay a leaf that does not import `ubyport` (pgx-heavy), and repointing them is a behaviour-neutral refactor with its own test run. Brief B in §10 repoints both and deletes the duplicates. Until then the golden file is the only guarantee, so the new package is the reference copy.
- Timezone: `time.LoadLocation("Europe/Prague")` plus `import _ "time/tzdata"` (stdlib, same as `ubyport`). `go/Dockerfile` runs on bare alpine without tzdata, so the import is required, not decoration.
- Naive time in Go: a `time.Time` in UTC whose clock fields are the Prague wall clock. `LocalNow(instant)` converts; the other functions take that wall clock as `now`. Python's "already naive `now`" path is the caller skipping `LocalNow`.

**Parity mechanism** (mirrors `App/scripts/validation_golden.py` + `go/internal/validation/testdata/golden.json`, and `App/tests/test_ical_golden.py`): the script `App/scripts/deadlines_golden.py` runs the real Python over fixed inputs and writes `go/internal/deadlines/testdata/golden.json`; the Go test embeds it and compares every case; a Python test regenerates in memory and compares to the committed file, so a change to `deadlines.py` that is not regenerated fails CI. Inputs: a full Mon-Sun week, DST end (25 Oct 2026) and start (29 Mar 2026), year, month, February/March and leap-day boundaries, summer time, and for each check-in 19 "now" values from 4 days before the deadline to 5 days after, including exactly at the deadline, one second before and after, exactly 24 h and 48 h out, the day before check-in, and naive values. `hours_left` floats are compared with `==`: both sides divide whole seconds by 3600.0.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/deadlines_golden.py` | create | writes the golden file from the real Python |
| `go/internal/deadlines/testdata/golden.json` | create (generated) | the golden cases |
| `go/internal/deadlines/deadlines.go` | create | the port |
| `go/internal/deadlines/deadlines_test.go` | create | compares Go to the golden file |
| `App/tests/test_deadlines_golden.py` | create | fails when the golden file is stale |
| `docs/tasks/1132-report.md` | create | the report (§9) |

No other file may change. `docs/context/test-map.md` and `architecture.md` are the orchestrator's (§10).

## 4. Steps

Work on the branch you are on (`claude/fervent-cray-1qsrfa`). Do not create another branch, do not push, do not open a PR; the orchestrator does that. After each step 1 to 5 run `git add <that step's file> && git commit -m "1132 step k"` (k = step number), nothing else staged.

0. Check anchors: `git branch --show-current; grep -n 'REPORTING_WORKING_DAYS = 3' App/app/deadlines.py; ls go/internal/deadlines App/scripts/deadlines_golden.py App/tests/test_deadlines_golden.py 2>&1 | tail -30`. Expected: branch `claude/fervent-cray-1qsrfa`; one grep line; the three `ls` paths "No such file or directory". Anything else: STOP (§8).

1. Create `App/scripts/deadlines_golden.py` with exactly this content:

```python
"""Write go/internal/deadlines/testdata/golden.json from the real Python deadlines.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/deadlines_golden.py

The Go test in go/internal/deadlines/ compares every case. A "now" ending in Z
is an aware UTC instant (Python converts it to Prague time); one without Z is
a naive Prague wall clock (Python uses it as it is).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from app import deadlines  # noqa: E402

OUT = APP.parent / "go" / "internal" / "deadlines" / "testdata" / "golden.json"
PRAGUE = ZoneInfo("Europe/Prague")
STAMP = "%Y-%m-%dT%H:%M:%S"


def _dates() -> list[date]:
    days: set[date] = set()
    for first, last in (
        ("2026-11-02", "2026-11-08"),  # a full week, Monday to Sunday
        ("2026-10-22", "2026-10-27"),  # DST ends Sunday 25 Oct
        ("2026-03-26", "2026-03-31"),  # DST starts Sunday 29 Mar
        ("2026-12-29", "2027-01-04"),  # year boundary
        ("2026-01-29", "2026-02-03"),  # month boundary
        ("2026-02-25", "2026-03-02"),  # February to March
        ("2024-02-27", "2024-03-01"),  # leap day
        ("2026-06-01", "2026-06-02"),  # summer time
    ):
        day = date.fromisoformat(first)
        while day <= date.fromisoformat(last):
            days.add(day)
            day += timedelta(days=1)
    return sorted(days)


def _nows(check_in: date) -> list[str]:
    due = datetime.combine(deadlines.add_working_days(check_in, 3), time(23, 59, 59))
    due_utc = due.replace(tzinfo=PRAGUE).astimezone(timezone.utc)
    out = [(due_utc + timedelta(seconds=s)).strftime(STAMP) + "Z" for s in (
        -4 * 86400, -2 * 86400 - 1, -2 * 86400, -86401, -86400, -3600, -1, 0, 1, 3600,
        47 * 3600, 2 * 86400, 5 * 86400 + 7)]
    midnight = datetime.combine(check_in, time(0, 0))
    out.append((midnight - timedelta(hours=12)).strftime(STAMP) + "Z")
    out.append((midnight + timedelta(hours=22, minutes=30)).strftime(STAMP) + "Z")
    out.append(midnight.strftime(STAMP))  # naive
    out.append((midnight + timedelta(hours=12)).strftime(STAMP))  # naive
    out.append(due.strftime(STAMP))  # naive, exactly at the deadline
    out.append((due + timedelta(seconds=1)).strftime(STAMP))  # naive, one second after
    return out


def _case(check_in: date, text: str) -> dict:
    if text.endswith("Z"):
        now = datetime.strptime(text[:-1], STAMP).replace(tzinfo=timezone.utc)
    else:
        now = datetime.strptime(text, STAMP)
    kind, amount = deadlines.time_left_parts(check_in, now)
    return {
        "check_in": check_in.isoformat(),
        "now": text,
        "local_now": deadlines.local_now(now).strftime(STAMP),
        "hours_left": deadlines.hours_left(check_in, now),
        "urgency": deadlines.urgency(check_in, now),
        "parts": [kind, amount],
        "describe": deadlines.describe_time_left(check_in, now),
    }


def _lines(rows: list) -> str:
    return "[\n" + ",\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n]"


def render() -> str:
    days = _dates()
    sections = {
        "working_days": [{"date": d.isoformat(), "working": deadlines.is_working_day(d)} for d in days],
        "add": [
            {"start": d.isoformat(), "count": n, "result": deadlines.add_working_days(d, n).isoformat()}
            for d in days
            for n in (0, 1, 3, 5)
        ],
        "deadlines": [
            {"check_in": d.isoformat(), "deadline": deadlines.reporting_deadline(d).strftime(STAMP)}
            for d in days
        ],
        "cases": [_case(d, text) for d in days for text in _nows(d)],
    }
    head = {
        "reporting_working_days": deadlines.REPORTING_WORKING_DAYS,
        "urgency_order": deadlines.URGENCY_ORDER,
    }
    body = ",\n".join(f'"{name}": {_lines(rows)}' for name, rows in sections.items())
    return "{\n" + json.dumps(head, sort_keys=True)[1:-1] + ",\n" + body + "\n}\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")
```

   Command: `python3 -c "import ast,sys;ast.parse(open('App/scripts/deadlines_golden.py').read());print('ok')" | tail -30`. Expected: `ok`. Commit "1132 step 1".

2. Generate the golden file (do not edit it by hand). From `App/`: `if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi; $PY scripts/deadlines_golden.py 2>&1 | tail -30`. Expected: `wrote .../go/internal/deadlines/testdata/golden.json`. Then from the repo root: `wc -l go/internal/deadlines/testdata/golden.json | tail -30`. Expected: about 1111 lines (more than 1000). If the script fails on a missing module, create the venv as the script docstring says and retry once. Commit "1132 step 2" (file: the golden.json).

3. Create `go/internal/deadlines/deadlines.go` with exactly this content:

```go
// Package deadlines is the statutory three-working-day reporting deadline,
// ported from App/app/deadlines.py. The Python file is the reference: every
// function here must give the same answer as its Python twin, and
// testdata/golden.json (written by App/scripts/deadlines_golden.py from the
// real Python) is compared in deadlines_test.go.
//
// Nothing calls this package yet. Times are "naive" like Python's naive
// datetimes: a time.Time in UTC whose clock fields are the Prague wall clock.
// LocalNow turns a real instant into that wall clock; the other functions take
// the wall clock as `now`.
package deadlines

import (
	"fmt"
	"math"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container
)

// ReportingWorkingDays is deadlines.REPORTING_WORKING_DAYS.
const ReportingWorkingDays = 3

// UrgencyOrder is deadlines.URGENCY_ORDER.
var UrgencyOrder = map[string]int{"overdue": 0, "urgent": 1, "soon": 2, "ok": 3, "future": 4}

var prague = mustLoadPrague()

func mustLoadPrague() *time.Location {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		panic("deadlines: embedded Prague zone missing: " + err.Error())
	}
	return loc
}

// dateOnly keeps the Y/M/D of t and drops the clock and the zone.
func dateOnly(t time.Time) time.Time {
	y, m, d := t.Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

// IsWorkingDay is deadlines.is_working_day: Monday to Friday. Public holidays
// count as working days (decision 2026-10-31). The Y/M/D of day are used.
func IsWorkingDay(day time.Time) bool {
	wd := dateOnly(day).Weekday()
	return wd != time.Saturday && wd != time.Sunday
}

// AddWorkingDays is deadlines.add_working_days: the date (UTC midnight) the
// count-th working day of a window opening on start falls on. The start day is
// the first working day when it is one; a weekend start opens the count on the
// next working day.
func AddWorkingDays(start time.Time, count int) time.Time {
	current := dateOnly(start)
	remaining := count
	if IsWorkingDay(current) {
		remaining = count - 1
	}
	for remaining > 0 {
		current = current.AddDate(0, 0, 1)
		if IsWorkingDay(current) {
			remaining--
		}
	}
	return current
}

// ReportingDeadline is deadlines.reporting_deadline: 23:59:59 on the third
// working day of the window that opens on checkIn, as a naive time.
func ReportingDeadline(checkIn time.Time) time.Time {
	day := AddWorkingDays(checkIn, ReportingWorkingDays)
	return time.Date(day.Year(), day.Month(), day.Day(), 23, 59, 59, 0, time.UTC)
}

// LocalNow is deadlines.local_now for an instant: the naive Prague wall clock.
// (Python also accepts an already naive value and returns it unchanged; here
// the caller simply passes that value on without calling LocalNow.)
func LocalNow(now time.Time) time.Time {
	l := now.In(prague)
	return time.Date(l.Year(), l.Month(), l.Day(), l.Hour(), l.Minute(), l.Second(), l.Nanosecond(), time.UTC)
}

// HoursLeft is deadlines.hours_left. now is the naive Prague wall clock.
func HoursLeft(checkIn, now time.Time) float64 {
	return ReportingDeadline(checkIn).Sub(now).Seconds() / 3600.0
}

// Urgency is deadlines.urgency: "future", "ok", "soon", "urgent" or "overdue".
func Urgency(checkIn, now time.Time) string {
	if dateOnly(checkIn).After(dateOnly(now)) {
		return "future"
	}
	left := HoursLeft(checkIn, now)
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

// TimeLeftParts is deadlines.time_left_parts: (kind, amount) for the countdown.
func TimeLeftParts(checkIn, now time.Time) (string, int) {
	if dateOnly(checkIn).After(dateOnly(now)) {
		return "arrives_days", int(dateOnly(checkIn).Sub(dateOnly(now)) / (24 * time.Hour))
	}
	left := HoursLeft(checkIn, now)
	if left < 0 {
		over := math.Abs(left)
		if over < 48 {
			return "overdue_hours", int(over)
		}
		return "overdue_days", int(math.Floor(over / 24))
	}
	if left < 48 {
		return "hours_left", int(left)
	}
	return "days_left", int(math.Floor(left / 24))
}

// DescribeTimeLeft is deadlines.describe_time_left: the English countdown the
// Python app writes into logs and stored alert text. It is data, not host UI
// copy (templates use TimeLeftParts), so it ports byte for byte.
func DescribeTimeLeft(checkIn, now time.Time) string {
	kind, amount := TimeLeftParts(checkIn, now)
	switch kind {
	case "arrives_days":
		s := "s"
		if amount == 1 {
			s = ""
		}
		return fmt.Sprintf("arrives in %d day%s", amount, s)
	case "overdue_hours":
		return fmt.Sprintf("overdue by %d h", amount)
	case "overdue_days":
		return fmt.Sprintf("overdue by %d days", amount)
	case "hours_left":
		return fmt.Sprintf("%d h left", amount)
	}
	return fmt.Sprintf("%d days left", amount)
}
```

   Command, from `go/`: `test -z "$(gofmt -l .)" && go vet ./internal/deadlines/ 2>&1 | tail -30`. Expected: no output. Commit "1132 step 3".

4. Create `go/internal/deadlines/deadlines_test.go` with exactly this content:

```go
package deadlines

import (
	_ "embed"
	"encoding/json"
	"testing"
	"time"
)

// golden.json is written by App/scripts/deadlines_golden.py from the Python
// functions in App/app/deadlines.py.
//
//go:embed testdata/golden.json
var goldenJSON []byte

type golden struct {
	WorkingDays  int            `json:"reporting_working_days"`
	UrgencyOrder map[string]int `json:"urgency_order"`
	Days         []struct {
		Date    string `json:"date"`
		Working bool   `json:"working"`
	} `json:"working_days"`
	Add []struct {
		Start  string `json:"start"`
		Count  int    `json:"count"`
		Result string `json:"result"`
	} `json:"add"`
	Deadlines []struct {
		CheckIn  string `json:"check_in"`
		Deadline string `json:"deadline"`
	} `json:"deadlines"`
	Cases []struct {
		CheckIn   string        `json:"check_in"`
		Now       string        `json:"now"`
		LocalNow  string        `json:"local_now"`
		HoursLeft float64       `json:"hours_left"`
		Urgency   string        `json:"urgency"`
		Parts     []interface{} `json:"parts"`
		Describe  string        `json:"describe"`
	} `json:"cases"`
}

const (
	dateLayout  = "2006-01-02"
	stampLayout = "2006-01-02T15:04:05"
)

func loadGolden(t *testing.T) golden {
	t.Helper()
	var g golden
	if err := json.Unmarshal(goldenJSON, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func mustDate(t *testing.T, s string) time.Time {
	t.Helper()
	d, err := time.Parse(dateLayout, s)
	if err != nil {
		t.Fatal(err)
	}
	return d
}

func TestConstantsMatchPython(t *testing.T) {
	g := loadGolden(t)
	if g.WorkingDays != ReportingWorkingDays {
		t.Errorf("working days %d, Python %d", ReportingWorkingDays, g.WorkingDays)
	}
	if len(g.UrgencyOrder) != len(UrgencyOrder) {
		t.Fatalf("urgency order %v, Python %v", UrgencyOrder, g.UrgencyOrder)
	}
	for k, v := range g.UrgencyOrder {
		if UrgencyOrder[k] != v {
			t.Errorf("urgency order %q: %d, Python %d", k, UrgencyOrder[k], v)
		}
	}
}

func TestWorkingDaysMatchPython(t *testing.T) {
	g := loadGolden(t)
	if len(g.Days) < 40 {
		t.Fatalf("only %d working-day cases", len(g.Days))
	}
	for _, c := range g.Days {
		if got := IsWorkingDay(mustDate(t, c.Date)); got != c.Working {
			t.Errorf("%s: working %v, Python %v", c.Date, got, c.Working)
		}
	}
}

func TestAddWorkingDaysMatchPython(t *testing.T) {
	g := loadGolden(t)
	if len(g.Add) < 160 {
		t.Fatalf("only %d add cases", len(g.Add))
	}
	for _, c := range g.Add {
		got := AddWorkingDays(mustDate(t, c.Start), c.Count).Format(dateLayout)
		if got != c.Result {
			t.Errorf("%s + %d: %s, Python %s", c.Start, c.Count, got, c.Result)
		}
	}
}

func TestReportingDeadlineMatchesPython(t *testing.T) {
	g := loadGolden(t)
	if len(g.Deadlines) < 40 {
		t.Fatalf("only %d deadline cases", len(g.Deadlines))
	}
	for _, c := range g.Deadlines {
		got := ReportingDeadline(mustDate(t, c.CheckIn)).Format(stampLayout)
		if got != c.Deadline {
			t.Errorf("check-in %s: %s, Python %s", c.CheckIn, got, c.Deadline)
		}
	}
}

func TestCountdownMatchesPython(t *testing.T) {
	g := loadGolden(t)
	if len(g.Cases) < 500 {
		t.Fatalf("only %d countdown cases", len(g.Cases))
	}
	kinds := map[string]bool{}
	for _, c := range g.Cases {
		checkIn := mustDate(t, c.CheckIn)
		var now time.Time
		if n := len(c.Now); c.Now[n-1] == 'Z' {
			instant, err := time.Parse(stampLayout, c.Now[:n-1])
			if err != nil {
				t.Fatal(err)
			}
			now = LocalNow(instant)
		} else {
			var err error
			if now, err = time.Parse(stampLayout, c.Now); err != nil {
				t.Fatal(err)
			}
		}
		id := c.CheckIn + " at " + c.Now
		if got := now.Format(stampLayout); got != c.LocalNow {
			t.Errorf("%s: local now %s, Python %s", id, got, c.LocalNow)
		}
		if got := HoursLeft(checkIn, now); got != c.HoursLeft {
			t.Errorf("%s: hours left %v, Python %v", id, got, c.HoursLeft)
		}
		if got := Urgency(checkIn, now); got != c.Urgency {
			t.Errorf("%s: urgency %s, Python %s", id, got, c.Urgency)
		}
		kind, amount := TimeLeftParts(checkIn, now)
		if kind != c.Parts[0].(string) || float64(amount) != c.Parts[1].(float64) {
			t.Errorf("%s: parts (%s, %d), Python %v", id, kind, amount, c.Parts)
		}
		kinds[kind] = true
		if got := DescribeTimeLeft(checkIn, now); got != c.Describe {
			t.Errorf("%s: describe %q, Python %q", id, got, c.Describe)
		}
	}
	for _, k := range []string{"arrives_days", "hours_left", "days_left", "overdue_hours", "overdue_days"} {
		if !kinds[k] {
			t.Errorf("the golden file never reaches kind %q", k)
		}
	}
}

// Monday check-in: Wednesday 23:59:59 (decision D3), not Thursday.
func TestMondayCheckInEndsWednesday(t *testing.T) {
	got := ReportingDeadline(mustDate(t, "2026-11-02")).Format(stampLayout)
	if got != "2026-11-04T23:59:59" {
		t.Errorf("got %s", got)
	}
}

// 2026-03-29 01:00 UTC is 03:00 Prague (the clocks jumped from 02:00).
func TestLocalNowAcrossSpringForward(t *testing.T) {
	before := LocalNow(time.Date(2026, 3, 29, 0, 59, 59, 0, time.UTC)).Format(stampLayout)
	after := LocalNow(time.Date(2026, 3, 29, 1, 0, 0, 0, time.UTC)).Format(stampLayout)
	if before != "2026-03-29T01:59:59" || after != "2026-03-29T03:00:00" {
		t.Errorf("before %s, after %s", before, after)
	}
}
```

   Command, from `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/deadlines/ -count=1 2>&1 | tail -30`. Expected: `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines`. If a case fails, do not change the golden file or the expectations: the Python is right, STOP and report the first failing line (§8). Commit "1132 step 4".

5. Create `App/tests/test_deadlines_golden.py` with exactly this content:

```python
"""The Go deadlines package reads go/internal/deadlines/testdata/golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "deadlines_golden", APP_DIR / "scripts" / "deadlines_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deadlines_golden_matches_python_deadlines():
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"check_in"') >= 500
```

   Command, from `App/`: `.venv/bin/python -m pytest tests/test_deadlines.py tests/test_deadlines_golden.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass, 0 failed (if `.venv` is missing, create it as `scripts/deadlines_golden.py`'s docstring says). Commit "1132 step 5".

6. Write `docs/tasks/1132-report.md` (§9), set `Status: review` in this brief, then `git add docs/tasks/1132-report.md docs/tasks/1132-go-deadlines-package.md && git commit -m "1132 step 6"`.

## 5. Do not touch

`App/app/` (all of it; `deadlines.py` stays as it is), `go/internal/ubyport/`, `go/internal/calendar/`, `go/go.mod`, `go/go.sum`, `go/Dockerfile`, `.github/`, `docs/context/`, every other file not in §3. Hard rules 1 to 5 above. No new dependency, no network call, no SQL, no env var.

## 6. Commands

From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/deadlines/ -count=1 2>&1 | tail -30` (the same three CI runs, narrowed to the new package; CI runs `go test ./...`).
From `App/` (the [test-map](../context/test-map.md) "Filing, UbyPort, claim" row names `test_deadline*.py`; run only these two): `.venv/bin/python -m pytest tests/test_deadlines.py tests/test_deadlines_golden.py -q --tb=short -x 2>&1 | tail -30`.
Golden freshness: from `App/`, `.venv/bin/python scripts/deadlines_golden.py && git status --short ../go | tail -30` shows no change after step 2's commit.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/deadlines/ -count=1` passes.
- [ ] From `App/`: `scripts/deadlines_golden.py` re-run leaves `git status --short ../go` empty, and `pytest tests/test_deadlines.py tests/test_deadlines_golden.py` passes.
- [ ] From the repo root: `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat "$(git log -1 --format=%H --grep=^Brief.1132)"..HEAD | tail -30` lists only the §3 paths.
- [ ] Six commits "1132 step 1" to "1132 step 6" on `claude/fervent-cray-1qsrfa`; nothing pushed.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in step 0 is not found, or a §3 file already exists;
- a Go test case fails (never edit golden.json or the Python to make it pass), or any test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- you need push, merge, a PR, secrets, SSH or deploy (the orchestrator or owner does that).

## 9. Report

Write `docs/tasks/1132-report.md` (600 tokens at most) with: 1. `git diff --stat "$(git log -1 --format=%H --grep=^Brief.1132)"..HEAD` (last 10 lines); 2. each command in §6 with the last 5 lines of its output; 3. §7 ticked; 4. deviations.

## 10. Later briefs (not this one)

Each depends on this one being merged. The first three are the order for the job; the last two are follow-ups.

- A: repoint `ubyport.ReportingDeadline` and `calendar.localNow/urgency` to `deadlines`, delete the duplicates, run their existing tests.
- B: Go port of `reporting.check_deadlines` (alert raising), with its SQL through the Go db layer and a parity test.
- C: Go port of `dsr.raise_due_alerts`.
- D: Go port of `filing_watchdog.run` (mails and heartbeat; highest filing risk, so it ships last and behind a switch).
- E: new job kind `deadlines` in the Go scheduler, an env switch between the Python and Go job, then removal of `scheduler._job_deadlines` once the Go job has run clean.
