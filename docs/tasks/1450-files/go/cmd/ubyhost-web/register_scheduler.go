package main

// Thread "Move scheduler to Go" (plan step J7) owns this file. With
// UBYHOST_SCHEDULER=go the Go service enqueues every job kind on the schedule
// of App/app/scheduler.py (go/internal/scheduler); with any other value it
// does nothing and Python's APScheduler keeps enqueuing.
//
// main.go has no hook for a background task, so this rides on registerRoutes
// and adds no route: run() calls newMux once, after the schema check, with
// the real pool. The tests call newMux with a nil pool, which starts nothing.
// The scheduler stops on SIGINT or SIGTERM, the signals run() stops on. A
// kill between two enqueues loses nothing: each enqueue is one INSERT.

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/scheduler"
)

func init() { registerRoutes(startScheduler) }

var schedulerOnce sync.Once

// startScheduler starts the Go scheduler once per process when it is
// switched on and a pool exists. A bad configuration is logged and nothing
// starts; Python refuses UBYHOST_SCHEDULER=go on the same configuration, so
// the worker container stops too and the problem is visible.
func startScheduler(_ *http.ServeMux, _ *metrics, pool *pgxpool.Pool) {
	if pool == nil || !scheduler.Enabled(os.Getenv) {
		return
	}
	schedulerOnce.Do(func() {
		plan, loc, err := scheduler.Setup(os.Getenv)
		if err != nil {
			slog.Error("scheduler not started", "owner", "go", "error", err.Error())
			return
		}
		state := scheduler.NewState(plan, loc, time.Now())
		enqueue := func(ctx context.Context, kind string) (bool, error) {
			return scheduler.Enqueue(ctx, pool, kind)
		}
		ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
		go func() {
			defer stop()
			scheduler.Run(ctx, state, enqueue, time.Now)
		}()
	})
}
