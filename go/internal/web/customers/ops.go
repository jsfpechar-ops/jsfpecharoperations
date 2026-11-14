package customers

// The counts of the operator console's "System problems" list. Python builds the
// whole of admin_ops.overview() (App/app/admin_ops.py 298-325) for GET /admin but
// admin_home.html prints only the six counts, so only the six counts are
// computed here, with the same queries: filings_needing_attention (80-124),
// stuck_submissions (127-157), feeds_needing_attention (160-203), job_health
// (206-242), mail_problems (245-274) and open_alerts (277-295). The rows, the
// ttlock block and every personal field those functions read are left out.

import (
	"context"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// OpsCounts is overview()["filings"|"stuck"|"feeds"|"jobs"|"mail"|"alerts"]["count"].
type OpsCounts struct {
	Filings, Stuck, Feeds, Jobs, Mail, Alerts int64
}

const (
	feedStaleHours      = 3
	runningStuckMinutes = 30
	mailStuckMinutes    = 30
	alertRowLimit       = 50 // ROW_LIMIT: open_alerts counts only the first 50 groups
	lastOKWriteMinutes  = 15 // scheduler.LAST_OK_WRITE_MINUTES
)

// jobIntervals is scheduler.job_intervals(): minutes between two runs of each job.
// The two polling intervals come from the environment, as in config.py.
func jobIntervals(getenv func(string) string) map[string]int {
	env := func(name string, fallback int) int {
		if n, err := strconv.Atoi(strings.TrimSpace(getenv(name))); err == nil {
			return n
		}
		return fallback
	}
	return map[string]int{
		"ical": env("UBYHOST_ICAL_POLL_MINUTES", 60), "submit": env("UBYHOST_SUBMIT_SWEEP_MINUTES", 10),
		"deadlines": 30, "mail": 5, "photo_sweep": 12 * 60, "meta_capi": 10, "retention": 24 * 60,
		"door_codes": 5, "posthog": 15, "push": 1, "guide_import": 60, "stay_fee_mail": 24 * 60,
		"stripe_sweep": 24 * 60, "billing_snapshot": 24 * 60,
	}
}

// lateAfterMinutes is scheduler.late_after_minutes.
func lateAfterMinutes(interval int) int {
	slack := 0
	if interval < lastOKWriteMinutes {
		slack = lastOKWriteMinutes
	}
	return 2*interval + slack
}

// parseOpsTime is admin_ops.parse_time: the ISO stamps the app writes, with or
// without an offset (none means UTC). Anything else is "no time".
func parseOpsTime(value string) (time.Time, bool) {
	text := strings.TrimSpace(value)
	if text == "" {
		return time.Time{}, false
	}
	if strings.HasSuffix(text, "Z") {
		text = text[:len(text)-1] + "+00:00"
	}
	for _, layout := range []string{
		"2006-01-02T15:04:05.999999999-07:00", "2006-01-02 15:04:05.999999999-07:00",
		"2006-01-02T15:04:05.999999999", "2006-01-02 15:04:05.999999999", "2006-01-02",
	} {
		if t, err := time.Parse(layout, text); err == nil {
			return t, true
		}
	}
	return time.Time{}, false
}

// ageMinutes is admin_ops.age_minutes: whole minutes, never negative; ok is false for "None".
func ageMinutes(value string, now time.Time) (int, bool) {
	t, ok := parseOpsTime(value)
	if !ok {
		return 0, false
	}
	m := int(now.Sub(t).Seconds() / 60)
	if now.Sub(t) < 0 {
		m = 0
	}
	return m, true
}

// Ops computes the six counts at the given moment.
func Ops(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (OpsCounts, error) {
	var out OpsCounts
	count := func(dst *int64, sql string, args ...any) error {
		return pool.QueryRow(ctx, sql, args...).Scan(dst)
	}
	// filings: reporting.ERROR, reporting.BLOCKED, reporting.SENT.
	if err := count(&out.Filings, `SELECT COUNT(DISTINCT r.id) FROM guest g
		JOIN reservation r ON r.id = g.reservation_id
		JOIN apartment a ON a.id = r.apartment_id
		LEFT JOIN submission s ON s.id = g.submission_id
		WHERE g.archived_at IS NULL AND r.archived_at IS NULL
		AND (g.submit_state IN ($1, $2) OR (s.state = 'outcome_unknown' AND g.submit_state <> $3))`,
		"error", "blocked", "sent"); err != nil {
		return out, err
	}
	running := stamp(at.Add(-runningStuckMinutes * time.Minute))
	if err := count(&out.Stuck, `SELECT COUNT(*) FROM submission WHERE state = 'running' AND created_at < $1`, running); err != nil {
		return out, err
	}
	feedCutoff := stamp(at.Add(-feedStaleHours * time.Hour))
	if err := count(&out.Feeds, `SELECT COUNT(*) FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id
		WHERE f.active = 1 AND a.active = 1 AND a.archived_at IS NULL
		AND (f.last_status IS NULL OR f.last_status <> 'ok'
		OR COALESCE(f.last_checked_at, f.last_sync_at) IS NULL
		OR COALESCE(f.last_checked_at, f.last_sync_at) < $1)`, feedCutoff); err != nil {
		return out, err
	}
	mailCutoff := stamp(at.Add(-mailStuckMinutes * time.Minute))
	if err := count(&out.Mail, `SELECT COUNT(*) FROM email_outbox WHERE state IN ('failed', 'bounced', 'complained')
		OR (state = 'queued' AND created_at < $1) OR (state = 'sending' AND updated_at < $1)`, mailCutoff); err != nil {
		return out, err
	}
	if err := count(&out.Alerts, `SELECT COALESCE(SUM(n), 0)::bigint FROM (SELECT COUNT(*) AS n FROM alert
		WHERE resolved_at IS NULL GROUP BY kind, level ORDER BY n DESC, kind LIMIT $1) groups`, int64(alertRowLimit)); err != nil {
		return out, err
	}
	jobs, err := jobCount(ctx, pool, getenv, at)
	out.Jobs = jobs
	return out, err
}

// jobCount is job_health()["count"]: jobs that are late (no success on record, or one
// older than twice the interval plus the write window) or that have an open job_failed alert.
func jobCount(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (int64, error) {
	intervals := jobIntervals(getenv)
	keys := make([]string, 0, len(intervals))
	for id := range intervals {
		keys = append(keys, "job_last_ok:"+id)
	}
	stored := map[string]string{}
	rows, err := pool.Query(ctx, `SELECT key, COALESCE(value, '') FROM settings WHERE key = ANY($1)`, keys)
	if err != nil {
		return 0, err
	}
	for rows.Next() {
		var k, v string
		if err := rows.Scan(&k, &v); err != nil {
			rows.Close()
			return 0, err
		}
		stored[k] = v
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	failed := map[string]bool{}
	frows, err := pool.Query(ctx, `SELECT COALESCE(dedupe_key, '') FROM alert WHERE kind = 'job_failed' AND resolved_at IS NULL LIMIT $1`, int64(alertRowLimit))
	if err != nil {
		return 0, err
	}
	for frows.Next() {
		var k string
		if err := frows.Scan(&k); err != nil {
			frows.Close()
			return 0, err
		}
		failed[k] = true
	}
	frows.Close()
	if err := frows.Err(); err != nil {
		return 0, err
	}
	var n int64
	for id, minutes := range intervals {
		age, ok := ageMinutes(stored["job_last_ok:"+id], at)
		if !ok || age > lateAfterMinutes(minutes) || failed["job_failed:"+id] {
			n++
		}
	}
	return n, nil
}

// ReviewAlertCount is len(incidents.open_review_alerts()).
func ReviewAlertCount(ctx context.Context, pool *pgxpool.Pool) (int64, error) {
	var n int64
	err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM alert WHERE kind = 'incident_review' AND resolved_at IS NULL`).Scan(&n)
	return n, err
}
