package main

import (
	"os"
	"strings"
	"testing"
)

func TestValidateJobConfigOK(t *testing.T) {
	t.Setenv("UBYHOST_GO_JOB_KINDS", allQueued)
	t.Setenv("UBYHOST_JOB_QUEUE_KINDS", allQueued)
	t.Setenv("UBYHOST_SCHEDULER", "go")
	t.Setenv("UBYHOST_ENABLE_SCHEDULER", "1")
	t.Setenv("UBYHOST_SUBMIT_SWEEP_MINUTES", "10")
	kinds, err := parseGoKinds(os.Getenv("UBYHOST_GO_JOB_KINDS"))
	if err != nil {
		t.Fatal(err)
	}
	if err := validateJobConfig(kinds, os.Getenv, os.LookupEnv); err != nil {
		t.Fatalf("valid config: %v", err)
	}
}

func TestValidateJobConfigQueueMissingGoKind(t *testing.T) {
	goOnly := strings.Replace(allQueued, ",push", "", 1)
	kinds, err := parseGoKinds(goOnly)
	if err != nil {
		t.Fatal(err)
	}
	err = validateJobConfig(kinds, noopGetenv, lookupMap(map[string]string{
		"UBYHOST_JOB_QUEUE_KINDS": allQueued,
	}))
	if err == nil || !strings.Contains(err.Error(), "missing kinds queued for Go: push") {
		t.Fatalf("want missing push in GO kinds, got %v", err)
	}
}

func TestValidateJobConfigGoOutsideQueue(t *testing.T) {
	kinds, err := parseGoKinds("push")
	if err != nil {
		t.Fatal(err)
	}
	err = validateJobConfig(kinds, noopGetenv, lookupMap(map[string]string{
		"UBYHOST_JOB_QUEUE_KINDS": "",
	}))
	if err == nil || !strings.Contains(err.Error(), "must also be in UBYHOST_JOB_QUEUE_KINDS: push") {
		t.Fatalf("want go outside queue, got %v", err)
	}
}

func TestValidateJobConfigSchedulerMissingQueued(t *testing.T) {
	queue := strings.Replace(allQueued, ",push", "", 1)
	kinds, err := parseGoKinds(queue)
	if err != nil {
		t.Fatal(err)
	}
	err = validateJobConfig(kinds, schedGoGetenv, lookupMap(map[string]string{
		"UBYHOST_JOB_QUEUE_KINDS":      queue,
		"UBYHOST_SCHEDULER":            "go",
		"UBYHOST_SUBMIT_SWEEP_MINUTES": "10",
	}))
	if err == nil || !strings.Contains(err.Error(), "missing: push") {
		t.Fatalf("want scheduler queue check, got %v", err)
	}
}

func TestValidateJobConfigPaymentsRetiredPlan(t *testing.T) {
	queue := strings.Replace(allQueued, ",stripe_sweep", "", 1)
	kinds, err := parseGoKinds(queue)
	if err != nil {
		t.Fatal(err)
	}
	lookup := lookupMap(map[string]string{
		"UBYHOST_JOB_QUEUE_KINDS":      queue,
		"UBYHOST_SCHEDULER":            "go",
		"UBYHOST_PAYMENTS_RETIRED":     "1",
		"UBYHOST_SUBMIT_SWEEP_MINUTES": "10",
	})
	if err := validateJobConfig(kinds, schedGoGetenv, lookup); err != nil {
		t.Fatalf("payments retired 14-kind plan: %v", err)
	}
}

func lookupMap(env map[string]string) func(string) (string, bool) {
	return func(k string) (string, bool) {
		v, ok := env[k]
		return v, ok
	}
}

func noopGetenv(string) string { return "" }

func schedGoGetenv(k string) string {
	if k == "UBYHOST_SCHEDULER" {
		return "go"
	}
	return ""
}
