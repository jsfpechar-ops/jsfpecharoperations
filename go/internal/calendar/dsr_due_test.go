package calendar

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"strings"
	"testing"
	"time"
)

type dsrDueRun struct {
	Today  string       `json:"today"`
	Raised int          `json:"raised"`
	Alerts []watchAlert `json:"alerts"`
}

type dsrDueGolden struct {
	SeedCreated  string           `json:"seed_created"`
	SeedResolved string           `json:"seed_resolved"`
	Seed         []watchSeedTable `json:"seed"`
	Runs         []dsrDueRun      `json:"runs"`
}

// TestRaiseDSRDueAlertsMatchesPython seeds the golden requests, runs
// RaiseDSRDueAlerts for every golden day and compares the return value and
// every alert row with what dsr.raise_due_alerts did on the same rows. It reuses
// the seed and snapshot helpers of watch_test.go.
func TestRaiseDSRDueAlertsMatchesPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/dsr_due_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g dsrDueGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Runs) < 2 || len(g.Seed) == 0 {
		t.Fatal("golden file has fewer than two runs or no seed")
	}
	wg := watchGolden{SeedCreated: g.SeedCreated, SeedResolved: g.SeedResolved, Seed: g.Seed}
	pool := dbPool(t)
	seeded := watchSeed(t, pool, wg)
	for i, run := range g.Runs {
		today, err := time.Parse("2006-01-02", run.Today)
		if err != nil {
			t.Fatal(err)
		}
		raised, err := RaiseDSRDueAlerts(context.Background(), pool, today)
		if err != nil {
			t.Fatalf("run %d: %v", i+1, err)
		}
		if raised != run.Raised {
			t.Errorf("run %d: raised %d, Python raised %d", i+1, raised, run.Raised)
		}
		got := watchLines(t, watchSnapshot(t, pool, wg, seeded))
		want := watchLines(t, run.Alerts)
		if strings.Join(got, "\n") != strings.Join(want, "\n") {
			t.Errorf("run %d alerts differ from Python\n got:\n%s\nwant:\n%s", i+1,
				strings.Join(got, "\n"), strings.Join(want, "\n"))
		}
	}
}
