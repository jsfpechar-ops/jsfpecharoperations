// The deadlines job: App/app/scheduler.py _job_deadlines in Go. It runs the
// deadline watch (check_deadlines, then raise_due_alerts), then the filing
// watchdog even when the watch failed, then pings the filing heartbeat.
package calendar

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

// DeadlinesSummary holds the counts of one deadlines run, as _log_run logs them.
type DeadlinesSummary struct {
	Alerts      int
	RequestsDue int
	Watchdog    WatchdogResult
}

// deadlinesSteps are the parts of one run; tests replace them.
type deadlinesSteps struct {
	check       func() (int, error)
	dsrDue      func() (int, error)
	watchdog    func() (WatchdogResult, error)
	raiseFailed func() error
	ping        func(url string)
	getenv      func(string) string
}

// RunDeadlinesJob is _job_deadlines for the Go job queue. at is the instant of
// the run; ping GETs the filing heartbeat URL (jobs.Ping in production). A
// failed watch or watchdog raises the critical job_failed alert at once, as
// Python's _job_failed does, and returns an error so the queue does not record
// a success. A failed watchdog sends no heartbeat at all.
func RunDeadlinesJob(ctx context.Context, pool *pgxpool.Pool, lookupEnv func(string) (string, bool), at time.Time, ping func(url string)) (DeadlinesSummary, error) {
	getenv := func(name string) string {
		v, _ := lookupEnv(name)
		return v
	}
	return runDeadlines(deadlinesSteps{
		check: func() (int, error) { return CheckDeadlines(ctx, pool, getenv, at, nil) },
		// Python's date.today() is the server's local date (TZ unset: UTC).
		dsrDue:      func() (int, error) { return RaiseDSRDueAlerts(ctx, pool, at.Local()) },
		watchdog:    func() (WatchdogResult, error) { return RunFilingWatchdog(ctx, pool, lookupEnv, at) },
		raiseFailed: func() error { return jobs.RaiseFailed(ctx, pool, "deadlines") },
		ping:        ping,
		getenv:      getenv,
	})
}

func runDeadlines(s deadlinesSteps) (DeadlinesSummary, error) {
	var sum DeadlinesSummary
	watchErr := func() error {
		n, err := s.check()
		if err != nil {
			return err
		}
		sum.Alerts = n
		n, err = s.dsrDue()
		if err != nil {
			return err
		}
		sum.RequestsDue = n
		return nil
	}()
	if watchErr != nil {
		slog.Error("deadline watch failed", "error", fmt.Sprintf("%T", watchErr))
		deadlinesRaiseFailed(s)
	} else if sum.Alerts > 0 || sum.RequestsDue > 0 {
		slog.Info("deadline watch", "alerts", sum.Alerts, "requests_due", sum.RequestsDue)
	}
	// WP23: the watchdog runs even when the watch failed; its mails and its
	// heartbeat reach the owner when the app itself is not being looked at.
	w, err := s.watchdog()
	if err != nil {
		// No ping at all: the external monitor alerts on the missing ping.
		slog.Error("filing watchdog failed", "error", fmt.Sprintf("%T", err))
		deadlinesRaiseFailed(s)
		if watchErr != nil {
			return sum, fmt.Errorf("deadline watch: %w; filing watchdog: %v", watchErr, err)
		}
		return sum, fmt.Errorf("filing watchdog: %w", err)
	}
	sum.Watchdog = w
	if w != (WatchdogResult{}) {
		slog.Info("filing watchdog", "at_risk", w.AtRisk, "not_sent", w.NotSent, "unknown_risk", w.UnknownRisk,
			"awaiting_retry", w.AwaitingRetry, "host_mails", w.HostMails, "digest", w.Digest)
	}
	// A failed deadline watch counts as a failure too: nobody is being told.
	if url := FilingHeartbeatURL(s.getenv, w.AtRisk > 0 || watchErr != nil); url != "" {
		s.ping(url)
	}
	if watchErr != nil {
		return sum, fmt.Errorf("deadline watch: %w", watchErr)
	}
	return sum, nil
}

func deadlinesRaiseFailed(s deadlinesSteps) {
	if err := s.raiseFailed(); err != nil {
		slog.Error("job_failed alert not raised", "job", "deadlines")
	}
}
