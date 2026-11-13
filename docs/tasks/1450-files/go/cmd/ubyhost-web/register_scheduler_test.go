package main

import (
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/scheduler"
)

// With a nil pool (tests, newMux) nothing starts, switched on or not.
func TestSchedulerNeedsPool(t *testing.T) {
	t.Setenv("UBYHOST_SCHEDULER", "go")
	startScheduler(nil, nil, nil)
	newMux(&metrics{counts: map[key]int64{}}, nil)
}

// Every kind the Go service runs (UBYHOST_GO_JOB_KINDS) is one the Go
// scheduler enqueues, and each has a backoff interval equal to its schedule
// interval (cron kinds: one day).
func TestSchedulerCoversEveryGoKind(t *testing.T) {
	plan, err := scheduler.Plan(func(string) string { return "" })
	if err != nil {
		t.Fatal(err)
	}
	every := map[string]int{}
	for _, tr := range plan {
		if tr.Daily() {
			every[tr.Kind] = 24 * 60
		} else {
			every[tr.Kind] = int(tr.Every.Minutes())
		}
	}
	for kind := range goHandlers(nil) {
		m, ok := every[kind]
		if !ok {
			t.Errorf("%s runs in Go but is not scheduled", kind)
			continue
		}
		if goIntervals[kind] != m {
			t.Errorf("%s: backoff interval %d, schedule %d", kind, goIntervals[kind], m)
		}
	}
}
