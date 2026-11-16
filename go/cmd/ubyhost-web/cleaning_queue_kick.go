package main

// After a host saves or removes a cleaning TTLock code, run one cleaner-queue pass in the
// background so the lock is updated in seconds. The 5-minute door_codes job stays as the
// fallback and the retry path. The pass runs only when the Go job owns the queue.

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	doorcleaning "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes/cleaning"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/cleaning"
)

var (
	cleaningKickMu   sync.Mutex
	cleaningKickOnce sync.Once
	cleaningKickDeps doorcleaning.QueueDeps
	cleaningKickErr  error
	// cleaningQueuePass is replaced in tests.
	cleaningQueuePass = runCleaningQueuePass
)

func init() {
	registerRoutes(func(_ *http.ServeMux, _ *metrics, pool *pgxpool.Pool) {
		cleaning.SetQueueKick(func() { cleaningKick(pool) })
	})
}

// goOwnsDoorCodes is true when door codes are on and door_codes is a Go job kind.
func goOwnsDoorCodes(getenv func(string) string) bool {
	if !doorCodesOn(getenv("UBYHOST_DOOR_CODES")) {
		return false
	}
	for _, k := range strings.Split(getenv("UBYHOST_GO_JOB_KINDS"), ",") {
		if strings.TrimSpace(k) == "door_codes" {
			return true
		}
	}
	return false
}

// cleaningKick returns at once. The pass runs in a goroutine; a pass already running makes
// this a no-op (the 5-minute job covers anything missed).
func cleaningKick(pool *pgxpool.Pool) {
	if !goOwnsDoorCodes(os.Getenv) {
		return
	}
	go func() {
		if !cleaningKickMu.TryLock() {
			return
		}
		defer cleaningKickMu.Unlock()
		ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
		defer cancel()
		if err := cleaningQueuePass(ctx, pool); err != nil {
			slog.Warn("cleaning queue kick failed", "err", err)
		}
	}()
}

// runCleaningQueuePass builds the deps once, then runs one ProcessQueue pass.
func runCleaningQueuePass(ctx context.Context, pool *pgxpool.Pool) error {
	cleaningKickOnce.Do(func() {
		parts, err := newDoorCodesParts(pool)
		if err != nil {
			cleaningKickErr = err
			return
		}
		cleaningKickDeps = doorcleaning.QueueDeps{
			TTLock:         parts.Client,
			Cipher:         parts.Keys,
			Clock:          systemClock{},
			StagingNoLogin: stagingNoLogin(os.Getenv),
		}
	})
	if cleaningKickErr != nil {
		return cleaningKickErr
	}
	_, err := doorcleaning.ProcessQueue(ctx, pool, cleaningKickDeps)
	return err
}
