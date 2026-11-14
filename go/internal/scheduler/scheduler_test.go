package scheduler

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

func env(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

func lookup(m map[string]string) func(string) (string, bool) {
	return func(k string) (string, bool) { v, ok := m[k]; return v, ok }
}

func byKind(t *testing.T, plan []Trigger, kind string) Trigger {
	t.Helper()
	for _, tr := range plan {
		if tr.Kind == kind {
			return tr
		}
	}
	t.Fatalf("no trigger %s", kind)
	return Trigger{}
}

// fires drives a fresh State with a fake clock that jumps to each wake-up and
// returns the first n run times of kind.
func fires(t *testing.T, plan []Trigger, start time.Time, kind string, n int) []time.Time {
	t.Helper()
	s := NewState(plan, prague(t), start)
	var out []time.Time
	for len(out) < n {
		wake := s.NextWake()
		for _, k := range s.Due(wake) {
			if k == kind {
				out = append(out, wake)
			}
		}
	}
	return out
}

func local(t *testing.T, y int, mo time.Month, d, h, mi int) time.Time {
	return time.Date(y, mo, d, h, mi, 0, 0, prague(t))
}

// Spring forward (2026-03-29, 02:00 CET to 03:00 CEST): each cron job runs at
// its local time that day, 23 hours after the day before.
func TestDailyAcrossSpringForward(t *testing.T) {
	plan := defaultPlan(t)
	start := local(t, 2026, 3, 27, 12, 0)
	for _, c := range []struct {
		kind   string
		hh, mm int
	}{{"retention", 3, 30}, {"stripe_sweep", 4, 15}, {"billing", 6, 0}, {"billing_snapshot", 6, 15}, {"stay_fee_mail", 7, 0}} {
		got := fires(t, plan, start, c.kind, 4)
		for i, day := range []int{28, 29, 30, 31} {
			if want := local(t, 2026, 3, day, c.hh, c.mm); !got[i].Equal(want) {
				t.Fatalf("%s run %d: %s, want %s", c.kind, i, got[i].In(prague(t)), want)
			}
		}
		if gap := got[1].Sub(got[0]); gap != 23*time.Hour {
			t.Fatalf("%s: gap over the change %v", c.kind, gap)
		}
		if gap := got[2].Sub(got[1]); gap != 24*time.Hour {
			t.Fatalf("%s: gap after the change %v", c.kind, gap)
		}
	}
}

// Fall back (2026-10-25, 03:00 CEST to 02:00 CET): each cron job runs once,
// 25 hours after the day before; retention at 03:30 CET, after the repeat.
func TestDailyAcrossFallBack(t *testing.T) {
	plan := defaultPlan(t)
	start := local(t, 2026, 10, 23, 12, 0)
	got := fires(t, plan, start, "retention", 4)
	for i, day := range []int{24, 25, 26, 27} {
		if want := local(t, 2026, 10, day, 3, 30); !got[i].Equal(want) {
			t.Fatalf("retention run %d: %s, want %s", i, got[i].In(prague(t)), want)
		}
	}
	if gap := got[1].Sub(got[0]); gap != 25*time.Hour {
		t.Fatalf("gap over the change %v", gap)
	}
	if got[1].UTC().Format("15:04") != "02:30" {
		t.Fatalf("03:30 CET is 02:30 UTC, got %s", got[1].UTC())
	}
}

// Interval jobs count elapsed time: the submit sweep stays 10 minutes apart
// while the wall clock jumps an hour forward or back.
func TestIntervalIgnoresDaylightSaving(t *testing.T) {
	plan := defaultPlan(t)
	for _, start := range []time.Time{local(t, 2026, 3, 29, 1, 31), local(t, 2026, 10, 25, 1, 31)} {
		got := fires(t, plan, start, "submit", 12)
		if !got[0].Equal(start.Add(10 * time.Minute)) {
			t.Fatalf("first submit %s", got[0])
		}
		for i := 1; i < len(got); i++ {
			if gap := got[i].Sub(got[i-1]); gap != 10*time.Minute {
				t.Fatalf("start %s run %d: gap %v", start, i, gap)
			}
		}
	}
}

func TestFirstRuns(t *testing.T) {
	plan := defaultPlan(t)
	start := local(t, 2026, 6, 1, 6, 0)
	s := NewState(plan, prague(t), start)
	want := map[string]time.Time{
		"ical":        start.Add(20 * time.Second),
		"photo_sweep": start.Add(20 * time.Second),
		"submit":      start.Add(10 * time.Minute),
		"push":        start.Add(time.Minute),
		"billing":     start, // a cron time equal to the start runs at once
		"retention":   local(t, 2026, 6, 2, 3, 30),
	}
	for i, tr := range s.plan {
		if w, ok := want[tr.Kind]; ok && !s.due[i].Equal(w) {
			t.Errorf("%s first %s, want %s", tr.Kind, s.due[i], w)
		}
	}
}

// After a long stall each kind is due once (coalesce) and its next run is
// on its old grid after now, as APScheduler computes it.
func TestCoalesceAfterAStall(t *testing.T) {
	plan := defaultPlan(t)
	start := local(t, 2026, 5, 4, 10, 0)
	s := NewState(plan, prague(t), start)
	now := start.Add(3*time.Hour + 30*time.Second)
	got := s.Due(now)
	if len(got) != 10 { // the ten interval kinds; the five cron times are tomorrow
		t.Fatalf("due %v", got)
	}
	seen := map[string]int{}
	for _, k := range got {
		seen[k]++
	}
	for _, k := range []string{"push", "submit", "ical", "mail", "deadlines"} {
		if seen[k] != 1 {
			t.Fatalf("%s due %d times", k, seen[k])
		}
	}
	for _, k := range []string{"retention", "billing", "stay_fee_mail"} {
		if seen[k] != 0 {
			t.Fatalf("%s due before its time", k)
		}
	}
	push := byKind(t, plan, "push")
	for i, tr := range s.plan {
		if tr.Kind == push.Kind && !s.due[i].Equal(start.Add(3*time.Hour+time.Minute)) {
			t.Fatalf("next push %s", s.due[i])
		}
		if tr.Kind == "submit" && !s.due[i].Equal(start.Add(3*time.Hour+10*time.Minute)) {
			t.Fatalf("next submit %s", s.due[i])
		}
	}
	if again := s.Due(now); len(again) != 0 {
		t.Fatalf("due again at the same instant: %v", again)
	}
}

// The interval variables take what Python's int() takes; values Python
// rejects, or at or below 0 (Python then refuses the switch), are refused.
func TestPlanReadsTheTwoIntervals(t *testing.T) {
	plan, err := Plan(lookup(map[string]string{"UBYHOST_ICAL_POLL_MINUTES": " 30 ", "UBYHOST_SUBMIT_SWEEP_MINUTES": "5"}))
	if err != nil {
		t.Fatal(err)
	}
	if byKind(t, plan, "ical").Every != 30*time.Minute || byKind(t, plan, "submit").Every != 5*time.Minute {
		t.Fatalf("intervals not read")
	}
	for raw, want := range map[string]int{"+7": 7, "1_0": 10, "007": 7, "\t12\n": 12} {
		plan, err := Plan(lookup(map[string]string{"UBYHOST_SUBMIT_SWEEP_MINUTES": raw}))
		if err != nil || byKind(t, plan, "submit").Every != time.Duration(want)*time.Minute {
			t.Fatalf("%q: %v %v", raw, plan, err)
		}
	}
	for _, bad := range []string{"", " ", "0", "-0", "-5", "ten", "1.5", "_1", "1_", "1__0", "+", "1 0"} {
		if _, err := Plan(lookup(map[string]string{"UBYHOST_SUBMIT_SWEEP_MINUTES": bad})); err == nil {
			t.Fatalf("%q accepted", bad)
		}
	}
}

func TestEnabled(t *testing.T) {
	for v, want := range map[string]bool{"go": true, " Go ": true, "GO": true, "": false, "python": false, "1": false, "go,python": false} {
		if got := Enabled(env(map[string]string{"UBYHOST_SCHEDULER": v})); got != want {
			t.Errorf("%q: %v", v, got)
		}
	}
}

func TestSetupNeedsEveryKindQueued(t *testing.T) {
	all := "ical,submit,deadlines,mail,photo_sweep,meta_capi,retention,stay_fee_mail,stripe_sweep,billing,billing_snapshot,door_codes,posthog,push,guide_import"
	plan, loc, err := Setup(lookup(map[string]string{"UBYHOST_JOB_QUEUE_KINDS": all}))
	if err != nil || len(plan) != 15 || loc.String() != Timezone {
		t.Fatalf("%d %v %v", len(plan), loc, err)
	}
	_, _, err = Setup(lookup(map[string]string{"UBYHOST_JOB_QUEUE_KINDS": strings.Replace(all, "door_codes,", "", 1)}))
	if err == nil || !strings.Contains(err.Error(), "missing: door_codes") {
		t.Fatalf("got %v", err)
	}
	if _, _, err := Setup(lookup(nil)); err == nil {
		t.Fatal("empty queue kinds accepted")
	}
}

// Run enqueues on time, keeps going after a failed enqueue and stops with
// its context.
func TestRunEnqueuesAndStops(t *testing.T) {
	plan := []Trigger{{Kind: "push", Every: 20 * time.Millisecond}}
	s := NewState(plan, prague(t), time.Now())
	ctx, cancel := context.WithCancel(context.Background())
	calls := make(chan string, 10)
	n := 0
	enqueue := func(_ context.Context, kind string) (bool, error) {
		n++
		calls <- kind
		if n == 1 {
			return false, errors.New("database down")
		}
		return true, nil
	}
	added0, failed0 := Counts()
	done := make(chan struct{})
	go func() { Run(ctx, s, enqueue, time.Now); close(done) }()
	for i := 0; i < 3; i++ {
		select {
		case k := <-calls:
			if k != "push" {
				t.Fatalf("kind %s", k)
			}
		case <-time.After(2 * time.Second):
			t.Fatal("no enqueue")
		}
	}
	cancel()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("Run did not stop")
	}
	if added, failed := Counts(); failed-failed0 != 1 || added-added0 < 2 {
		t.Fatalf("counts added %d failed %d", added, failed)
	}
}
