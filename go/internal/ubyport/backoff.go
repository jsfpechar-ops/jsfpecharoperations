package ubyport

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"
	_ "time/tzdata" // Europe/Prague without a system zoneinfo

	"github.com/jackc/pgx/v5/pgxpool"
)

// Retry policy for definite transport failures (A1b P1). Python twin:
// App/app/reporting.py transport_backoff_from_rows. The gap after chain length n
// is 10 min (n=1), 30 min (n=2), 60 min (n>=3). At most transportDailyCap
// attempts per apartment per Prague day; after that the next try is 00:10 Prague
// the next day. auth is not part of the chain (the auth pause wins).
const (
	transportEscalateAfter = 3
	transportDailyCap      = 24
)

var (
	transportGaps    = []time.Duration{10 * time.Minute, 30 * time.Minute}
	transportGapLong = 60 * time.Minute
)

// TransportRow is one submission of an apartment, newest first.
type TransportRow struct {
	State, Cause, Mode, FinishedAt string
}

// isManualMode is true for the modes of a host's manual send (manual, manual_bulk,
// manual_resend). Manual sends ignore the gap and never count toward the daily cap.
func isManualMode(mode string) bool {
	return strings.HasPrefix(mode, "manual")
}

// transportChain is the leading run of transport_error rows that are not auth.
func transportChain(rows []TransportRow) []TransportRow {
	for i, r := range rows {
		if r.State != "transport_error" || r.Cause == "auth" {
			return rows[:i]
		}
	}
	return rows
}

// TransportChainLength is the number of consecutive transport failures.
func TransportChainLength(rows []TransportRow) int {
	return len(transportChain(rows))
}

// TransportBackoffFromRows returns the earliest next automatic try and whether one
// is owed at all. The caller waits while now is before the returned time.
func TransportBackoffFromRows(rows []TransportRow, now time.Time) (time.Time, bool) {
	chain := transportChain(rows)
	if len(chain) == 0 {
		return time.Time{}, false
	}
	last, err := time.Parse(time.RFC3339, chain[0].FinishedAt)
	if err != nil {
		return time.Time{}, false
	}
	gap := transportGapLong
	if n := len(chain); n <= len(transportGaps) {
		gap = transportGaps[n-1]
	}
	candidate := last.Add(gap)
	zone, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		return candidate, true
	}
	y, m, d := now.In(zone).Date()
	count := 0
	for _, r := range chain {
		if isManualMode(r.Mode) {
			continue
		}
		t, err := time.Parse(time.RFC3339, r.FinishedAt)
		if err != nil {
			continue
		}
		if ty, tm, td := t.In(zone).Date(); ty == y && tm == m && td == d {
			count++
		}
	}
	if count >= transportDailyCap {
		return time.Date(y, m, d+1, 0, 10, 0, 0, zone).UTC(), true
	}
	return candidate, true
}

// loadTransportRows reads the apartment's last 500 submissions, newest first.
func loadTransportRows(ctx context.Context, pool *pgxpool.Pool, aptID int64) ([]TransportRow, error) {
	rows, err := pool.Query(ctx,
		`SELECT state, COALESCE(cause, ''), COALESCE(mode, ''), COALESCE(finished_at, '')
		   FROM submission WHERE apartment_id = $1 ORDER BY id DESC LIMIT 500`, aptID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []TransportRow
	for rows.Next() {
		var r TransportRow
		if err := rows.Scan(&r.State, &r.Cause, &r.Mode, &r.FinishedAt); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// TransportBackoffUntil applies the policy to the apartment's submissions. The
// sweep calls it before ClaimSendable; a manual send does not.
func TransportBackoffUntil(ctx context.Context, pool *pgxpool.Pool, aptID int64, now time.Time) (time.Time, bool, error) {
	rows, err := loadTransportRows(ctx, pool, aptID)
	if err != nil {
		return time.Time{}, false, err
	}
	until, ok := TransportBackoffFromRows(rows, now)
	return until, ok, nil
}

// escalateTransportChain is the escalation of reporting.py (A1b P1): when the chain
// reaches transportEscalateAfter, queue one support copy, idempotent per submission.
// Best-effort: it cannot fail the filing.
func escalateTransportChain(ctx context.Context, d BatchDeps, ref ApartmentRef, subID int64, msg, cause string) {
	rows, err := loadTransportRows(ctx, d.Pool, ref.ID)
	if err != nil {
		log.Printf("transport_chain_read_failed apartment_id=%d err=%v", ref.ID, err)
		return
	}
	if TransportChainLength(rows) != transportEscalateAfter {
		return
	}
	if _, err := queueSubmissionProblem(ctx, d.Pool, d.Getenv, d.AppBaseURL, d.PublicBaseURL,
		ref, subID, "transport_error", msg, true, time.Now().UTC(), unknownSupportCC,
		fmt.Sprintf("submission_transport_repeated:%d", subID), cause); err != nil {
		log.Printf("submission_transport_repeated_mail_failed apartment_id=%d submission_id=%d", ref.ID, subID)
	}
}

// transportNextTryText is the "next" alert param: the next automatic try in UTC, or "" when none is owed.
func transportNextTryText(ctx context.Context, pool *pgxpool.Pool, aptID int64) string {
	until, owed, err := TransportBackoffUntil(ctx, pool, aptID, time.Now().UTC())
	if err != nil || !owed {
		return ""
	}
	return until.UTC().Format("2006-01-02 15:04 UTC")
}
