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
