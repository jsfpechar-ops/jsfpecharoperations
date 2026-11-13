package scheduler

import (
	"encoding/json"
	"os"
	"sort"
	"testing"
	"time"
)

// golden is testdata/python_schedule.json, written by
// App/scripts/scheduler_golden.py from the real scheduler.start() and the
// real APScheduler triggers.
type golden struct {
	Timezone     string         `json:"timezone"`
	JobKinds     []string       `json:"job_kinds"`
	JobIntervals map[string]int `json:"job_intervals"`
	Jobs         []struct {
		Kind         string         `json:"kind"`
		Trigger      string         `json:"trigger"`
		Args         map[string]int `json:"args"`
		FirstDelay   *int           `json:"first_delay_seconds"`
		MaxInstances int            `json:"max_instances"`
		Coalesce     bool           `json:"coalesce"`
	} `json:"jobs"`
	Windows []struct {
		StartUTC string `json:"start_utc"`
		Jobs     []struct {
			Kind  string `json:"kind"`
			Fires []struct {
				UTC   string `json:"utc"`
				Local string `json:"local"`
			} `json:"fires"`
		} `json:"jobs"`
	} `json:"windows"`
}

const pyUTC = "2006-01-02T15:04:05.000000-07:00"

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/python_schedule.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func prague(t *testing.T) *time.Location {
	t.Helper()
	loc, err := time.LoadLocation(Timezone)
	if err != nil {
		t.Fatal(err)
	}
	return loc
}

func defaultPlan(t *testing.T) []Trigger {
	t.Helper()
	plan, err := Plan(func(string) string { return "" })
	if err != nil {
		t.Fatal(err)
	}
	return plan
}

// The Go plan has Python's kinds, order, trigger types and arguments.
func TestPlanMatchesPythonAddJobCalls(t *testing.T) {
	g := loadGolden(t)
	if g.Timezone != Timezone {
		t.Fatalf("timezone %q", g.Timezone)
	}
	plan := defaultPlan(t)
	if len(plan) != len(g.Jobs) {
		t.Fatalf("go %d triggers, python %d", len(plan), len(g.Jobs))
	}
	var kinds []string
	for i, tr := range plan {
		j := g.Jobs[i]
		kinds = append(kinds, tr.Kind)
		if tr.Kind != j.Kind {
			t.Fatalf("trigger %d: go %s, python %s", i, tr.Kind, j.Kind)
		}
		if j.MaxInstances != 1 || !j.Coalesce {
			t.Errorf("%s: python max_instances %d coalesce %v", j.Kind, j.MaxInstances, j.Coalesce)
		}
		switch j.Trigger {
		case "interval":
			if tr.Daily() || len(j.Args) != 1 || time.Duration(j.Args["minutes"])*time.Minute != tr.Every {
				t.Errorf("%s: go every %v, python %v", tr.Kind, tr.Every, j.Args)
			}
			if tr.Every != time.Duration(g.JobIntervals[tr.Kind])*time.Minute {
				t.Errorf("%s: job_intervals() says %d", tr.Kind, g.JobIntervals[tr.Kind])
			}
		case "cron":
			if !tr.Daily() || len(j.Args) != 2 || j.Args["hour"] != tr.Hour || j.Args["minute"] != tr.Minute {
				t.Errorf("%s: go %02d:%02d, python %v", tr.Kind, tr.Hour, tr.Minute, j.Args)
			}
		default:
			t.Errorf("%s: python trigger %q", tr.Kind, j.Trigger)
		}
		wantFirst := time.Duration(0)
		if j.FirstDelay != nil {
			wantFirst = time.Duration(*j.FirstDelay) * time.Second
		}
		if tr.FirstAfter != wantFirst {
			t.Errorf("%s: go first after %v, python %v", tr.Kind, tr.FirstAfter, wantFirst)
		}
	}
	sort.Strings(kinds)
	if len(kinds) != len(g.JobKinds) {
		t.Fatalf("go kinds %v, python JOB_KINDS %v", kinds, g.JobKinds)
	}
	for i := range kinds {
		if kinds[i] != g.JobKinds[i] {
			t.Fatalf("go kinds %v, python JOB_KINDS %v", kinds, g.JobKinds)
		}
	}
}

// Every fire time APScheduler computes, from six starts (the nights of both
// 2026 daylight saving changes and a day before each, exactly at a cron time,
// a millisecond before one), is the fire time State gives, in UTC and in
// Prague local time.
func TestFireTimesMatchAPScheduler(t *testing.T) {
	g := loadGolden(t)
	loc := prague(t)
	plan := defaultPlan(t)
	for _, w := range g.Windows {
		start, err := time.Parse(pyUTC, w.StartUTC)
		if err != nil {
			t.Fatal(err)
		}
		want := map[string]int{}
		for _, j := range w.Jobs {
			want[j.Kind] = len(j.Fires)
		}
		got := map[string][]time.Time{}
		s := NewState(plan, loc, start)
		for done := 0; done < len(plan); {
			wake := s.NextWake()
			for _, kind := range s.Due(wake) {
				got[kind] = append(got[kind], wake)
				if len(got[kind]) == want[kind] {
					done++
				}
			}
		}
		for _, j := range w.Jobs {
			for i, f := range j.Fires {
				if i >= len(got[j.Kind]) {
					t.Fatalf("%s %s: go has only %d fires", w.StartUTC, j.Kind, len(got[j.Kind]))
				}
				g := got[j.Kind][i]
				if u := g.UTC().Format(pyUTC); u != f.UTC {
					t.Fatalf("%s %s fire %d: go %s, python %s", w.StartUTC, j.Kind, i, u, f.UTC)
				}
				if l := g.In(loc).Format(pyUTC); l != f.Local {
					t.Fatalf("%s %s fire %d: go local %s, python %s", w.StartUTC, j.Kind, i, l, f.Local)
				}
			}
		}
	}
}
