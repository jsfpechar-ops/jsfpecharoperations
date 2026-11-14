// Package scheduler enqueues job rows on the schedule of App/app/scheduler.py
// start(): the same 15 kinds, intervals, cron times and time zone. It is the
// Go side of the switch UBYHOST_SCHEDULER=go (plan step J7); with any other
// value nothing here runs and Python's APScheduler keeps enqueuing.
//
// APScheduler semantics kept (APScheduler 3.11.3, BackgroundScheduler with
// timezone Europe/Prague, every job max_instances=1, coalesce=True):
//   - interval trigger: elapsed time, not wall time, so a daylight saving
//     change neither shortens nor stretches it. The first run is one interval
//     after start, except ical and photo_sweep (next_run_time=_soon(): 20 s).
//   - cron trigger (hour, minute): the local wall time in Europe/Prague each
//     day; none of the five cron times falls in a daylight saving gap or
//     repeat, so each runs once a day, 23 or 25 hours apart on change days.
//   - coalesce: runs missed while the process was late collapse into one.
//   - no catch-up across a restart: the schedule starts again from the
//     process start, as APScheduler's memory job store does.
//
// One deliberate difference: APScheduler skips a run that starts more than
// 1 s late (misfire_grace_time 1). Go enqueues it late instead, once. Enqueue
// is idempotent (one open row per kind), so late is harmless and dropping a
// submit or deadlines row is not.
package scheduler

import (
	"context"
	"fmt"
	"log/slog"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

// Timezone is config.TIMEZONE, the zone BackgroundScheduler gets.
const Timezone = "Europe/Prague"

// soon is scheduler._soon(): now plus 20 seconds.
const soon = 20 * time.Second

// enqueueTimeout bounds one INSERT so a stuck database cannot stall the loop.
const enqueueTimeout = 10 * time.Second

// Trigger is one add_job call of scheduler.start(). Every > 0 is an interval
// trigger; Every == 0 is a daily cron trigger at Hour:Minute:00 local time.
type Trigger struct {
	Kind       string
	Every      time.Duration
	FirstAfter time.Duration // 0: the first run is Every after start
	Hour       int
	Minute     int
}

// Daily reports whether t is a cron trigger.
func (t Trigger) Daily() bool { return t.Every == 0 }

// Enabled reads UBYHOST_SCHEDULER: true only for "go" (case and spaces
// ignored), the same test App/app/scheduler.py makes.
func Enabled(getenv func(string) string) bool {
	return strings.ToLower(strings.TrimSpace(getenv("UBYHOST_SCHEDULER"))) == "go"
}

// pyInt is Python's int(text) for ASCII digits: surrounding white space, an
// optional sign, and single underscores between digits ("1_0" is 10).
// Python also takes non-ASCII digits; Go refuses them, and the Python
// worker's watch (App/app/scheduler.py watch_go_scheduler) covers that
// one difference by enqueuing itself and raising the alert.
func pyInt(text string) (int, bool) {
	s := strings.TrimSpace(text)
	sign := ""
	if s != "" && (s[0] == '+' || s[0] == '-') {
		sign, s = s[:1], s[1:]
	}
	if s == "" || s[0] == '_' || s[len(s)-1] == '_' || strings.Contains(s, "__") {
		return 0, false
	}
	n, err := strconv.Atoi(sign + strings.ReplaceAll(s, "_", ""))
	return n, err == nil
}

// minutesEnv reads one interval as config.py does: int(os.environ.get(name,
// def)). Unset gives def. A value Python's int() refuses (an empty string
// included) stops Python at import; one at or below 0 makes Python's
// go_scheduler_problem() refuse the switch. Go refuses both, so both sides
// agree that the switch is off and Python keeps enqueuing.
func minutesEnv(lookup func(string) (string, bool), name string, def int) (int, error) {
	raw, ok := lookup(name)
	if !ok {
		return def, nil
	}
	n, valid := pyInt(raw)
	if !valid || n <= 0 {
		return 0, fmt.Errorf("%s must be a whole number of minutes above 0", name)
	}
	return n, nil
}

// Plan lists the triggers in the order scheduler.start() adds them. Only
// ical and submit read the environment (UBYHOST_ICAL_POLL_MINUTES default 60,
// UBYHOST_SUBMIT_SWEEP_MINUTES default 10), as job_intervals() does. lookup
// is os.LookupEnv in production.
func Plan(lookup func(string) (string, bool)) ([]Trigger, error) {
	ical, err := minutesEnv(lookup, "UBYHOST_ICAL_POLL_MINUTES", 60)
	if err != nil {
		return nil, err
	}
	submit, err := minutesEnv(lookup, "UBYHOST_SUBMIT_SWEEP_MINUTES", 10)
	if err != nil {
		return nil, err
	}
	m := time.Minute
	return []Trigger{
		{Kind: "ical", Every: time.Duration(ical) * m, FirstAfter: soon},
		{Kind: "submit", Every: time.Duration(submit) * m},
		{Kind: "deadlines", Every: 30 * m},
		{Kind: "mail", Every: 5 * m},
		{Kind: "photo_sweep", Every: 12 * 60 * m, FirstAfter: soon},
		{Kind: "meta_capi", Every: 10 * m},
		{Kind: "retention", Hour: 3, Minute: 30},
		{Kind: "stay_fee_mail", Hour: 7, Minute: 0},
		{Kind: "stripe_sweep", Hour: 4, Minute: 15},
		{Kind: "billing", Hour: 6, Minute: 0},
		{Kind: "billing_snapshot", Hour: 6, Minute: 15},
		{Kind: "door_codes", Every: 5 * m},
		{Kind: "posthog", Every: 15 * m},
		{Kind: "push", Every: 1 * m},
		{Kind: "guide_import", Every: 60 * m},
	}, nil
}

// CheckQueued makes sure every planned kind is in UBYHOST_JOB_QUEUE_KINDS.
// A kind outside it runs in-process in Python, so a Go row for it would run
// it twice; Python's go_scheduler_problem() refuses the switch on the same
// condition and keeps enqueuing.
func CheckQueued(plan []Trigger, raw string) error {
	queued := map[string]bool{}
	for _, k := range strings.Split(raw, ",") {
		if k = strings.TrimSpace(k); k != "" {
			queued[k] = true
		}
	}
	var missing []string
	for _, t := range plan {
		if !queued[t.Kind] {
			missing = append(missing, t.Kind)
		}
	}
	if len(missing) > 0 {
		return fmt.Errorf("UBYHOST_SCHEDULER=go needs every job in UBYHOST_JOB_QUEUE_KINDS; missing: %s", strings.Join(missing, ", "))
	}
	return nil
}

// Setup reads the environment: the plan, the queue check and the zone.
func Setup(lookup func(string) (string, bool)) ([]Trigger, *time.Location, error) {
	plan, err := Plan(lookup)
	if err != nil {
		return nil, nil, err
	}
	queued, _ := lookup("UBYHOST_JOB_QUEUE_KINDS")
	if err := CheckQueued(plan, queued); err != nil {
		return nil, nil, err
	}
	loc, err := time.LoadLocation(Timezone)
	if err != nil {
		return nil, nil, err
	}
	return plan, loc, nil
}

// dailyAtOrAfter is the first Hour:Minute:00 in loc at or after t
// (CronTrigger.get_next_fire_time with no previous run).
func dailyAtOrAfter(tr Trigger, t time.Time, loc *time.Location) time.Time {
	l := t.In(loc)
	c := time.Date(l.Year(), l.Month(), l.Day(), tr.Hour, tr.Minute, 0, 0, loc)
	for c.Before(t) {
		l = l.AddDate(0, 0, 1)
		c = time.Date(l.Year(), l.Month(), l.Day(), tr.Hour, tr.Minute, 0, 0, loc)
	}
	return c
}

// first is the job's first run time for a scheduler started at start.
func first(tr Trigger, start time.Time, loc *time.Location) time.Time {
	if tr.Daily() {
		return dailyAtOrAfter(tr, start, loc)
	}
	if tr.FirstAfter > 0 {
		return start.Add(tr.FirstAfter)
	}
	return start.Add(tr.Every)
}

// next is the run after the one due at due, handled at now (now >= due).
// Missed runs are coalesced: the result is always after now.
func next(tr Trigger, due, now time.Time, loc *time.Location) time.Time {
	if now.Before(due) {
		now = due
	}
	if tr.Daily() {
		return dailyAtOrAfter(tr, now.Add(time.Nanosecond), loc)
	}
	n := due.Add(tr.Every)
	if !n.After(now) {
		skip := now.Sub(due) / tr.Every
		n = due.Add((skip + 1) * tr.Every)
	}
	return n
}

// State holds the next run time of every trigger.
type State struct {
	plan []Trigger
	due  []time.Time
	loc  *time.Location
}

// NewState starts the schedule at start, as BackgroundScheduler.start() does.
func NewState(plan []Trigger, loc *time.Location, start time.Time) *State {
	start = start.Round(0) // wall clock only, as APScheduler compares
	s := &State{plan: plan, due: make([]time.Time, len(plan)), loc: loc}
	for i, tr := range plan {
		s.due[i] = first(tr, start, loc)
	}
	return s
}

// NextWake is the earliest next run time of all triggers.
func (s *State) NextWake() time.Time {
	w := s.due[0]
	for _, d := range s.due[1:] {
		if d.Before(w) {
			w = d
		}
	}
	return w
}

// Due returns the kinds due at now, in plan order, once each, and moves each
// of them to its next run time.
func (s *State) Due(now time.Time) []string {
	now = now.Round(0)
	var kinds []string
	for i, tr := range s.plan {
		if s.due[i].After(now) {
			continue
		}
		kinds = append(kinds, tr.Kind)
		s.due[i] = next(tr, s.due[i], now, s.loc)
	}
	return kinds
}

// Enqueue adds a due row for kind unless one is already open, exactly as
// App/app/jobqueue.py enqueue does; true when a row was added. The partial
// unique index job_one_open_per_kind makes a second insert, from Go or from
// Python, a no-op while a row of that kind is open.
func Enqueue(ctx context.Context, pool *pgxpool.Pool, kind string) (bool, error) {
	now := jobs.Now(0)
	tag, err := pool.Exec(ctx,
		"INSERT INTO job (kind, run_at, payload, created_at) VALUES ($1, $2, '{}', $3) "+
			"ON CONFLICT (kind) WHERE done_at IS NULL AND dead_at IS NULL DO NOTHING",
		kind, now, now)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

// Counts of this process since start: rows added, and enqueues that failed
// (a failed enqueue is not retried, as in Python; the Python watch notices
// the missing row). Every failure log line carries the running total.
var enqueued, enqueueFailures atomic.Int64

// Counts returns the rows added and the failed enqueues since start.
func Counts() (added, failed int64) { return enqueued.Load(), enqueueFailures.Load() }

// EnqueueFunc enqueues one kind; Enqueue with a pool in production.
type EnqueueFunc func(ctx context.Context, kind string) (bool, error)

// Run enqueues every due kind until ctx is done. now is time.Now in
// production. A failed enqueue is logged and the schedule goes on, as
// APScheduler logs a failing job and keeps it scheduled.
func Run(ctx context.Context, s *State, enqueue EnqueueFunc, now func() time.Time) {
	slog.Info("scheduler started", "owner", "go", "kinds", len(s.plan), "timezone", s.loc.String())
	for {
		if wait := s.NextWake().Sub(now().Round(0)); wait > 0 {
			t := time.NewTimer(wait)
			select {
			case <-ctx.Done():
				t.Stop()
				slog.Info("scheduler stopped", "owner", "go")
				return
			case <-t.C:
			}
		}
		if ctx.Err() != nil {
			slog.Info("scheduler stopped", "owner", "go")
			return
		}
		for _, kind := range s.Due(now()) {
			ectx, cancel := context.WithTimeout(ctx, enqueueTimeout)
			added, err := enqueue(ectx, kind)
			cancel()
			if err != nil {
				n := enqueueFailures.Add(1)
				slog.Error("scheduler enqueue failed", "job", kind, "error", fmt.Sprintf("%T", err), "failed_total", n)
				continue
			}
			if added {
				enqueued.Add(1)
				slog.Info("scheduler enqueued", "job", kind)
			}
		}
	}
}
