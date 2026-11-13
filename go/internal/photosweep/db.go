package photosweep

// The three database steps of the photo sweep: reporting.purge_submission_payloads,
// guest_draft.purge and signup.purge (which calls meta_capi.expire_unsendable).

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	// submissionPayloadDays is reporting.SUBMISSION_PAYLOAD_DAYS.
	submissionPayloadDays = 90
	// draftMaxAgeDays is guest_draft.MAX_AGE_DAYS.
	draftMaxAgeDays = 7
	// unverifiedTTLDays is signup.UNVERIFIED_TTL_DAYS.
	unverifiedTTLDays = 7
	// metaSendWindow is meta_capi.SEND_WINDOW.
	metaSendWindow = 7*24*time.Hour - time.Hour
)

// terminalSubmissionStates is reporting.TERMINAL_SUBMISSION_STATES.
var terminalSubmissionStates = []string{"ok", "ok_duplicate", "partial", "error", "transport_error", "outcome_unknown"}

// clickPlatform is one entry of signup.PLATFORMS with its ID_COLUMNS and
// ID_RETENTION_DAYS (days after the click, days after an upload or send).
type clickPlatform struct {
	name        string
	columns     []string
	afterClick  int
	afterUpload int
}

// clickPlatforms is signup.PLATFORMS, in that order.
var clickPlatforms = []clickPlatform{
	{"google", []string{"gclid", "gbraid", "wbraid"}, 90, 30},
	{"meta", []string{"fbc", "client_user_agent"}, 90, 7},
}

// purgeSubmissionPayloads is reporting.purge_submission_payloads() for the
// global sweep: the envelopes of settled submissions older than 90 days are
// blanked. It returns the number of rows blanked and writes the retention
// audit line on every run, zero included.
func purgeSubmissionPayloads(ctx context.Context, pool *pgxpool.Pool, now time.Time) (int, error) {
	cutoff := iso(now.Add(-submissionPayloadDays * 24 * time.Hour))
	rows, err := pool.Query(ctx,
		`SELECT s.id FROM submission s JOIN apartment a ON a.id = s.apartment_id
		 WHERE s.created_at < $1 AND s.state = ANY($2)
		 AND (s.request_xml IS NOT NULL OR s.request_xml_enc IS NOT NULL OR s.response_xml IS NOT NULL)
		 ORDER BY s.id`,
		cutoff, terminalSubmissionStates)
	if err != nil {
		return 0, err
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return 0, err
		}
		ids = append(ids, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	if len(ids) == 0 {
		return 0, auditRetention(ctx, pool, now, "ubyport_xml", 0, cutoff)
	}
	if _, err := pool.Exec(ctx,
		`UPDATE submission SET request_xml = NULL, request_xml_enc = NULL, response_xml = NULL
		 WHERE id = ANY($1)`, ids); err != nil {
		return 0, err
	}
	detail := fmt.Sprintf("blanked the request and response envelope on %d submission(s) older than %d days",
		len(ids), submissionPayloadDays)
	if err := auditHost(ctx, pool, now, "submission_payload_purge", detail); err != nil {
		return 0, err
	}
	if err := auditRetention(ctx, pool, now, "ubyport_xml", len(ids), cutoff); err != nil {
		return 0, err
	}
	return len(ids), nil
}

// purgeGuestDrafts is guest_draft.purge(): a draft goes 7 days after its last
// change, or when its stay is no longer active or checked out before
// pragueToday (YYYY-MM-DD, claim.prague_today()).
func purgeGuestDrafts(ctx context.Context, pool *pgxpool.Pool, now time.Time, pragueToday string) (int, error) {
	tag, err := pool.Exec(ctx,
		`DELETE FROM guest_form_draft WHERE updated_at < $1 OR reservation_id IN
		 (SELECT r.id FROM reservation r WHERE r.status <> 'active' OR ubyhost_sqlite_date(r.date_to) < $2)`,
		iso(now.Add(-draftMaxAgeDays*24*time.Hour)), pragueToday)
	if err != nil {
		return 0, err
	}
	return int(tag.RowsAffected()), nil
}

// SignupCounts is the dict signup.purge returns.
type SignupCounts struct {
	UnverifiedDeleted int
	ClickIDsCleared   int
	MetaEventsExpired int
}

// expireUnsendableMeta duplicates meta_capi.expire_unsendable
// (App/app/meta_capi.py), which go/internal/metacapi/send.go also ports as the
// unexported expireUnsendable. Keep the three in step.
func expireUnsendableMeta(ctx context.Context, pool *pgxpool.Pool, now time.Time) (int, error) {
	tag, err := pool.Exec(ctx,
		`UPDATE ad_click SET send_state = $1, last_error = $2
		 WHERE platform = 'meta' AND send_state = $3 AND user_account_id IN (
		   SELECT id FROM user_account WHERE email_verified_at < $4)`,
		"expired", "older than Meta's 7-day event window", "pending", iso(now.Add(-metaSendWindow)))
	if err != nil {
		return 0, err
	}
	return int(tag.RowsAffected()), nil
}

// deleteUnverified is one iteration of signup.purge's per-account
// transaction (db.immediate()).
func deleteUnverified(ctx context.Context, pool *pgxpool.Pool, userID int64) error {
	return pgx.BeginFunc(ctx, pool, func(tx pgx.Tx) error {
		for _, sql := range []string{
			`DELETE FROM legal_acceptance WHERE user_account_id = $1`,
			`DELETE FROM ad_click WHERE user_account_id = $1`,
			`DELETE FROM email_outbox WHERE owner_user_id = $1`,
			`DELETE FROM audit WHERE owner_user_id = $1`,
			`DELETE FROM user_account WHERE id = $1 AND email_verified_at IS NULL AND active = 0`,
		} {
			if _, err := tx.Exec(ctx, sql, userID); err != nil {
				return err
			}
		}
		return nil
	})
}

// purgeSignups is signup.purge(): unconfirmed sign-ups older than 7 days go
// with their rows, unsendable Meta events expire, and click identifiers past
// their time are blanked, one platform per transaction.
func purgeSignups(ctx context.Context, pool *pgxpool.Pool, now time.Time) (SignupCounts, error) {
	var c SignupCounts
	daysAgo := func(days int) string { return iso(now.Add(-time.Duration(days) * 24 * time.Hour)) }
	rows, err := pool.Query(ctx,
		`SELECT id FROM user_account WHERE email_verified_at IS NULL
		 AND signup_at IS NOT NULL AND active = 0 AND signup_at < $1 ORDER BY id`,
		daysAgo(unverifiedTTLDays))
	if err != nil {
		return c, err
	}
	var stale []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return c, err
		}
		stale = append(stale, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return c, err
	}
	for _, id := range stale {
		if err := deleteUnverified(ctx, pool, id); err != nil {
			return c, err
		}
	}
	c.UnverifiedDeleted = len(stale)
	stamp := iso(now)
	if c.MetaEventsExpired, err = expireUnsendableMeta(ctx, pool, now); err != nil {
		return c, err
	}
	for _, p := range clickPlatforms {
		sets := make([]string, len(p.columns))
		for i, col := range p.columns {
			sets[i] = col + " = NULL"
		}
		var n int64
		err := pgx.BeginFunc(ctx, pool, func(tx pgx.Tx) error {
			tag, err := tx.Exec(ctx,
				`UPDATE ad_click SET `+strings.Join(sets, ", ")+`, ids_deleted_at = $1
				 WHERE platform = $2 AND ids_deleted_at IS NULL AND (
				 clicked_at < $3 OR uploaded_at < $4 OR withdrawn_at IS NOT NULL
				 OR send_state IN ('failed', 'expired'))`,
				stamp, p.name, daysAgo(p.afterClick), daysAgo(p.afterUpload))
			n = tag.RowsAffected()
			return err
		})
		if err != nil {
			return c, err
		}
		c.ClickIDsCleared += int(n)
	}
	return c, nil
}
