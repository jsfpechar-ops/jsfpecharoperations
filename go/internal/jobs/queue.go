// Package jobs is the Go consumer for the PostgreSQL job table. It follows
// App/app/jobqueue.py: same claim, lease, backoff and dead rules.
package jobs

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	LeaseMinutes = 60
	MaxAttempts  = 5
	drainLimit   = 50
	pollEvery    = 30 * time.Second
	defaultCap   = 60
)

var backoffMinutes = []int{1, 5, 15, 60}

// Handler runs one job and returns the number of rows it wrote.
type Handler func(ctx context.Context) (int, error)

// Job is a leased row.
type Job struct {
	ID       int64
	Kind     string
	Attempts int
}

var worker = workerID()

func workerID() string {
	host, _ := os.Hostname()
	return fmt.Sprintf("%s:%d", host, os.Getpid())
}

// Now returns the timestamp format of Python db.utcnow(), shifted by delta.
func Now(delta time.Duration) string {
	return time.Now().UTC().Add(delta).Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// Claim leases one due job of the given kinds; nil when none is due.
func Claim(ctx context.Context, pool *pgxpool.Pool, kinds []string) (*Job, error) {
	if len(kinds) == 0 {
		return nil, nil
	}
	now := Now(0)
	var j Job
	err := pool.QueryRow(ctx, `
		UPDATE job SET locked_at = $1, locked_by = $2, attempts = attempts + 1
		WHERE id = (
			SELECT id FROM job
			WHERE done_at IS NULL AND dead_at IS NULL AND run_at <= $3
			  AND (locked_at IS NULL OR locked_at < $4)
			  AND kind = ANY($5)
			ORDER BY run_at, id
			FOR UPDATE SKIP LOCKED
			LIMIT 1
		)
		RETURNING id, kind, attempts`,
		now, worker, now, Now(-LeaseMinutes*time.Minute), kinds,
	).Scan(&j.ID, &j.Kind, &j.Attempts)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &j, nil
}

// Finish records success; a row this worker no longer leases is left alone.
func Finish(ctx context.Context, pool *pgxpool.Pool, id int64) error {
	_, err := pool.Exec(ctx,
		"UPDATE job SET done_at = $1, locked_at = NULL, locked_by = NULL, error = NULL WHERE id = $2 AND locked_by = $3",
		Now(0), id, worker)
	return err
}

// Fail records a failure: retry with backoff, or dead after MaxAttempts.
// It returns true when the row just went dead.
func Fail(ctx context.Context, pool *pgxpool.Pool, j *Job, cause error, intervalMinutes int) (bool, error) {
	msg := []rune(cause.Error())
	if len(msg) > 300 {
		msg = msg[:300]
	}
	if j.Attempts >= MaxAttempts {
		_, err := pool.Exec(ctx,
			"UPDATE job SET dead_at = $1, error = $2, locked_at = NULL, locked_by = NULL WHERE id = $3 AND locked_by = $4",
			Now(0), string(msg), j.ID, worker)
		if err != nil {
			return false, err
		}
		return true, nil
	}
	step := backoffMinutes[min(j.Attempts-1, len(backoffMinutes)-1)]
	capMinutes := defaultCap
	if intervalMinutes > 0 {
		capMinutes = intervalMinutes
	}
	minutes := min(step, capMinutes)
	_, err := pool.Exec(ctx,
		"UPDATE job SET run_at = $1, error = $2, locked_at = NULL, locked_by = NULL WHERE id = $3 AND locked_by = $4",
		Now(time.Duration(minutes)*time.Minute), string(msg), j.ID, worker)
	return false, err
}

var jobNames = map[string]string{"billing_snapshot": "billing snapshot"}

// RaiseFailed opens the job_failed alert with the English copy of host_i18n,
// refreshing it when it is already open. Owner and apartment stay empty: it
// is a system alert.
func RaiseFailed(ctx context.Context, pool *pgxpool.Pool, kind string) error {
	name := jobNames[kind]
	if name == "" {
		name = kind
	}
	title := fmt.Sprintf("Background job '%s' failed.", name)
	detail := "Automatic reporting may be delayed until it runs again."
	key := "job_failed:" + kind
	tag, err := pool.Exec(ctx,
		"UPDATE alert SET level = $1, message = $2, detail = $3, params = NULL, created_at = $4 WHERE dedupe_key = $5 AND resolved_at IS NULL",
		"warning", title, detail, Now(0), key)
	if err != nil {
		return err
	}
	if tag.RowsAffected() > 0 {
		return nil
	}
	_, err = pool.Exec(ctx,
		"INSERT INTO alert (level, kind, dedupe_key, message, detail, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
		"warning", "job_failed", key, title, detail, Now(0))
	return err
}

// recordOK resolves the job_failed alert and stores job_last_ok:<kind>.
func recordOK(ctx context.Context, pool *pgxpool.Pool, kind string) {
	if _, err := pool.Exec(ctx,
		"UPDATE alert SET resolved_at = $1 WHERE dedupe_key = $2 AND resolved_at IS NULL",
		Now(0), "job_failed:"+kind); err != nil {
		slog.Warn("job alert resolve failed", "job", kind)
	}
	if _, err := pool.Exec(ctx,
		"INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
		"job_last_ok:"+kind, Now(0)); err != nil {
		slog.Warn("job last ok not recorded", "job", kind)
	}
}

// Run drains the given kinds at start and every 30 s until ctx is done.
func Run(ctx context.Context, pool *pgxpool.Pool, kinds []string, handlers map[string]Handler, intervals map[string]int) {
	ticker := time.NewTicker(pollEvery)
	defer ticker.Stop()
	for {
		drain(ctx, pool, kinds, handlers, intervals)
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

func drain(ctx context.Context, pool *pgxpool.Pool, kinds []string, handlers map[string]Handler, intervals map[string]int) int {
	ran := 0
	for i := 0; i < drainLimit && ctx.Err() == nil; i++ {
		j, err := Claim(ctx, pool, kinds)
		if err != nil {
			slog.Error("job claim failed", "error", fmt.Sprintf("%T", err))
			break
		}
		if j == nil {
			break
		}
		ran++
		start := time.Now()
		rows, runErr := handlers[j.Kind](ctx)
		ms := time.Since(start).Milliseconds()
		if runErr != nil {
			dead, err := Fail(ctx, pool, j, runErr, intervals[j.Kind])
			if err != nil {
				slog.Error("job failure not recorded", "job", j.Kind, "error", fmt.Sprintf("%T", err))
			}
			if dead {
				if err := RaiseFailed(ctx, pool, j.Kind); err != nil {
					slog.Error("job_failed alert not raised", "job", j.Kind)
				}
			}
			slog.Info("job run", "job", j.Kind, "ok", 0, "ms", ms, "rows", rows)
			continue
		}
		if err := Finish(ctx, pool, j.ID); err != nil {
			slog.Error("job finish not recorded", "job", j.Kind)
		}
		recordOK(ctx, pool, j.Kind)
		slog.Info("job run", "job", j.Kind, "ok", 1, "ms", ms, "rows", rows)
	}
	return ran
}
