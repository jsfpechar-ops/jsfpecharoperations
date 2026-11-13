package main

// Lane J (jobs) owns this file: add a Go job here, and only here.
// Interval and handler of one kind live together; kinds must not appear in
// register_filing.go (TestLaneKindsDisjoint).

import (
	"context"
	"log/slog"
	"net"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/metacapi"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/posthog"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pushsend"
)

// jobIntervals are the schedule intervals (minutes) that cap a retry backoff.
var jobIntervals = map[string]int{"billing_snapshot": 24 * 60, "stripe_sweep": 24 * 60, "ical": 60, "push": 1, "posthog": 15, "meta_capi": 10, "deadlines": 30}

// jobHandlers maps each lane-J job kind to its handler.
func jobHandlers(pool *pgxpool.Pool) map[string]jobs.Handler {
	return map[string]jobs.Handler{
		"billing_snapshot": func(ctx context.Context) (int, error) {
			return billing.WriteMonthSnapshot(ctx, pool, time.Now().UTC().Format("2006-01"), jobs.Now(0))
		},
		"stripe_sweep": func(ctx context.Context) (int, error) {
			expired, deleted, err := payments.Sweep(ctx, pool, time.Now().UTC(), jobs.Now(0))
			return expired + deleted, err
		},
		"ical": func(ctx context.Context) (int, error) {
			totals, err := ical.SyncAll(ctx, pool, os.Getenv, ical.FetchOptions{
				Resolver:     net.DefaultResolver,
				AllowPrivate: ical.AllowPrivate(os.Getenv),
			})
			if err == nil {
				jobs.Ping(ctx, os.Getenv("UBYHOST_HEARTBEAT_ICAL_URL"), "ical")
			}
			return totals.Feeds, err
		},
		"push": func(ctx context.Context) (int, error) {
			counts, err := (&pushsend.Sender{Pool: pool, Getenv: os.Getenv, Now: time.Now}).Drain(ctx, 50)
			total := 0
			for _, n := range counts {
				total += n
			}
			return total, err
		},
		"posthog": func(ctx context.Context) (int, error) {
			counts, err := posthog.Sync(ctx, pool, posthog.ConfigFromEnv(os.LookupEnv), nil, time.Now())
			if counts.Sent > 0 || counts.Failed > 0 {
				slog.Info("posthog sync", "sent", counts.Sent, "skipped", counts.Skipped, "failed", counts.Failed)
			}
			return counts.Sent, err
		},
		"meta_capi": func(ctx context.Context) (int, error) {
			sum, err := metacapi.Send(ctx, pool, metacapi.ConfigFromEnv(os.LookupEnv), nil, time.Now())
			if sum != (metacapi.Summary{}) {
				slog.Info("meta conversions", "sent", sum.Sent, "retry", sum.Retry, "failed", sum.Failed, "expired", sum.Expired)
			}
			return sum.Sent, err
		},
		"deadlines": func(ctx context.Context) (int, error) {
			sum, err := calendar.RunDeadlinesJob(ctx, pool, os.LookupEnv, time.Now(), func(url string) {
				jobs.Ping(ctx, url, "filing")
			})
			return sum.Alerts + sum.RequestsDue, err
		},
	}
}
