package main

import (
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/scheduler"
)

const allQueued = "ical,submit,deadlines,mail,photo_sweep,meta_capi,retention,stay_fee_mail,stripe_sweep,billing,billing_snapshot,door_codes,posthog,push,guide_import"

func TestSchedulerIsRegisteredAsBackgroundTask(t *testing.T) {
	n := 0
	for _, task := range backgroundTasks {
		if task.name == "scheduler" {
			n++
		}
	}
	if n != 1 {
		t.Fatalf("scheduler registered %d times", n)
	}
}

// Off: nothing to run. Bad configuration: an error, nothing to run. On and
// valid: a run function. The pool is nil: set-up never touches it.
func TestSchedulerTaskSetup(t *testing.T) {
	t.Setenv("UBYHOST_SCHEDULER", "")
	if run, err := schedulerTask(nil); run != nil || err != nil {
		t.Fatalf("off: %v %v", run != nil, err)
	}
	t.Setenv("UBYHOST_SCHEDULER", "go")
	t.Setenv("UBYHOST_JOB_QUEUE_KINDS", strings.Replace(allQueued, ",push", "", 1))
	if run, err := schedulerTask(nil); run != nil || err == nil || !strings.Contains(err.Error(), "missing: push") {
		t.Fatalf("missing kind: %v %v", run != nil, err)
	}
	t.Setenv("UBYHOST_JOB_QUEUE_KINDS", allQueued)
	t.Setenv("UBYHOST_SUBMIT_SWEEP_MINUTES", "0")
	if run, err := schedulerTask(nil); run != nil || err == nil {
		t.Fatalf("zero minutes: %v %v", run != nil, err)
	}
	t.Setenv("UBYHOST_SUBMIT_SWEEP_MINUTES", "10")
	if run, err := schedulerTask(nil); run == nil || err != nil {
		t.Fatalf("on: %v %v", run != nil, err)
	}
}

// Every kind the Go service runs (UBYHOST_GO_JOB_KINDS) is one the Go
// scheduler enqueues, and each has a backoff interval equal to its schedule
// interval (cron kinds: one day).
func TestSchedulerCoversEveryGoKind(t *testing.T) {
	plan, err := scheduler.Plan(func(string) (string, bool) { return "", false })
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
