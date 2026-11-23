package main

import (
	"fmt"
	"sort"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/scheduler"
)

func kindSet(raw string) map[string]bool {
	out := map[string]bool{}
	for _, k := range strings.Split(raw, ",") {
		if k = strings.TrimSpace(k); k != "" {
			out[k] = true
		}
	}
	return out
}

// validateJobConfig refuses startup when queue and Go job kind lists cannot
// enqueue and drain every Go handler. Python's worker used to cover gaps; the
// Go-only stack must fail loud instead.
func validateJobConfig(goKinds []string, getenv func(string) string, lookup func(string) (string, bool)) error {
	handlers := goHandlers(nil)
	goSet := map[string]bool{}
	for _, k := range goKinds {
		goSet[k] = true
	}
	queueRaw, _ := lookup("UBYHOST_JOB_QUEUE_KINDS")
	queueSet := kindSet(queueRaw)

	var unknown []string
	for k := range queueSet {
		if _, ok := handlers[k]; !ok {
			unknown = append(unknown, k)
		}
	}
	if len(unknown) > 0 {
		sort.Strings(unknown)
		return fmt.Errorf("UBYHOST_JOB_QUEUE_KINDS has unknown kinds: %s", strings.Join(unknown, ", "))
	}

	goOutside := make([]string, 0)
	for k := range goSet {
		if !queueSet[k] {
			goOutside = append(goOutside, k)
		}
	}
	if len(goOutside) > 0 {
		sort.Strings(goOutside)
		return fmt.Errorf("UBYHOST_GO_JOB_KINDS must also be in UBYHOST_JOB_QUEUE_KINDS: %s", strings.Join(goOutside, ", "))
	}

	if len(queueSet) > 0 {
		queueOutside := make([]string, 0)
		for k := range queueSet {
			if !goSet[k] {
				queueOutside = append(queueOutside, k)
			}
		}
		if len(queueOutside) > 0 {
			sort.Strings(queueOutside)
			return fmt.Errorf("UBYHOST_GO_JOB_KINDS is missing kinds queued for Go: %s", strings.Join(queueOutside, ", "))
		}
	}

	if scheduler.Enabled(getenv) && !killSwitch(getenv) {
		if _, _, err := scheduler.Setup(lookup); err != nil {
			return err
		}
	}
	return nil
}
