package main

import (
	"strings"
	"testing"
)

// UBYHOST_ENABLE_SCHEDULER stops the Go scheduler for exactly the values
// that stop Python (config.ENABLE_SCHEDULER: "0", "false", "no"; case and
// spaces count, unset or empty is on). Brief 1451.
func TestKillSwitchStopsTheGoScheduler(t *testing.T) {
	t.Setenv("UBYHOST_SCHEDULER", "go")
	t.Setenv("UBYHOST_JOB_QUEUE_KINDS", allQueued)
	for _, v := range []string{"0", "false", "no"} {
		t.Setenv("UBYHOST_ENABLE_SCHEDULER", v)
		run, err := schedulerTask(nil)
		if run != nil || err == nil || !strings.Contains(err.Error(), "UBYHOST_ENABLE_SCHEDULER="+v) {
			t.Fatalf("%q: run %v, err %v", v, run != nil, err)
		}
	}
	for _, v := range []string{"1", "", "yes", "False", "NO", " 0"} {
		t.Setenv("UBYHOST_ENABLE_SCHEDULER", v)
		if run, err := schedulerTask(nil); run == nil || err != nil {
			t.Fatalf("%q: run %v, err %v", v, run != nil, err)
		}
	}
}
