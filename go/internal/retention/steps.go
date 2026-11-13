package retention

// The steps of retention.STEPS, counting half. Each returns the count the
// Python step returns in a dry run. Brief 1211 adds the deleting half. SQL
// mirrors the Python statements on PostgreSQL: db.sqlite_date_expr(x) is
// ubyhost_sqlite_date(x), and "(? IS NULL OR col = ?)" is
// "($n::bigint IS NULL OR col = $n)".

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

func isUniqueViolation(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}

func (r *runner) scalar(ctx context.Context, sql string, args ...any) (int, error) {
	var n int64
	if err := r.pool.QueryRow(ctx, sql, args...).Scan(&n); err != nil {
		return 0, err
	}
	return int(n), nil
}

func (r *runner) ids(ctx context.Context, sql string, args ...any) ([]int64, error) {
	rows, err := r.pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, pgx.RowTo[int64])
}

// --- guests: housebook.expired_guest_ids -------------------------------------

const expiredGuestsSQL = `SELECT g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE COALESCE(ubyhost_sqlite_date(g.stay_to), ubyhost_sqlite_date(r.date_to)) < $1
	AND ($2::bigint IS NULL OR a.owner_user_id = $2) ORDER BY g.id`

func stepGuests(ctx context.Context, r *runner) (int, error) {
	ids, err := r.ids(ctx, expiredGuestsSQL, isoDate(housebookCutoff(r.today)), r.owner)
	return len(ids), err
}

// --- invoices: invoices.expired_ids -------------------------------------------

func stepInvoices(ctx context.Context, r *runner) (int, error) {
	ids, err := r.ids(ctx, `SELECT id FROM invoice WHERE issue_date < $1
		AND ($2::bigint IS NULL OR owner_user_id = $2)
		AND NOT EXISTS (SELECT 1 FROM invoice c WHERE c.corrects_invoice_id = invoice.id AND c.issue_date >= $1)
		ORDER BY CASE WHEN corrects_invoice_id IS NULL THEN 1 ELSE 0 END, id`, isoDate(invoiceCutoff(r.today)), r.owner)
	return len(ids), err
}

// --- platform_invoices: billing_invoices.expired_ids (global run only) --------

func stepPlatformInvoices(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	ids, err := r.ids(ctx, `SELECT id FROM platform_invoice WHERE issue_date < $1
		AND NOT EXISTS (SELECT 1 FROM platform_invoice c WHERE c.corrects_id = platform_invoice.id AND c.issue_date >= $1)
		ORDER BY CASE WHEN corrects_id IS NULL THEN 1 ELSE 0 END, id`, isoDate(invoiceCutoff(r.today)))
	return len(ids), err
}

// --- contact minimisation ----------------------------------------------------

func stepClaimEmails(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM reservation_claim WHERE email IS NOT NULL
		AND reservation_id IN (SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE ubyhost_sqlite_date(r.date_to) < $1 AND ($2::bigint IS NULL OR a.owner_user_id = $2))`,
		isoDate(r.daysAgo(claimEmailGraceDays)), r.owner)
}

func stepReservationContacts(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM reservation WHERE (guest_email IS NOT NULL OR phone_last4 IS NOT NULL)
		AND ubyhost_sqlite_date(date_to) < $1
		AND apartment_id IN (SELECT id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`,
		isoDate(r.daysAgo(claimEmailGraceDays)), r.owner)
}

func stepSubmitterIPs(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM guest WHERE filled_ip IS NOT NULL
		AND COALESCE(ubyhost_sqlite_date(stay_to), (SELECT ubyhost_sqlite_date(date_to) FROM reservation r2
			WHERE r2.id = guest.reservation_id)) < $1
		AND reservation_id IN (SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id
			WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`,
		isoDate(r.daysAgo(submitterIPGraceDays)), r.owner)
}

func stepEmptyReservations(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM reservation WHERE ubyhost_sqlite_date(date_to) < $1
		AND NOT EXISTS (SELECT 1 FROM guest g WHERE g.reservation_id = reservation.id)
		AND apartment_id IN (SELECT id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`,
		isoDate(housebookCutoff(r.today)), r.owner)
}

func stepStayFeeRecords(ctx context.Context, r *runner) (int, error) {
	year := fmt.Sprintf("%04d", housebookCutoff(r.today).Year())
	where := `substr(period_key, 1, 4) < $1
		AND apartment_id IN (SELECT id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`
	adjustments, err := r.scalar(ctx, `SELECT COUNT(*) FROM stay_fee_adjustment WHERE `+where, year, r.owner)
	if err != nil {
		return 0, err
	}
	filings, err := r.scalar(ctx, `SELECT COUNT(*) FROM stay_fee_filing WHERE `+where, year, r.owner)
	if err != nil {
		return 0, err
	}
	return adjustments + filings, nil
}

// --- logs and evidence -------------------------------------------------------

func stepAuditRows(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM audit WHERE at < $1
		AND action NOT IN ('legal_accepted', 'door_code_terms_accepted', 'leon_terms_accepted',
		'payments_terms_accepted') AND ($2::bigint IS NULL OR owner_user_id = $2)`,
		r.daysAgoISO(r.cfg.AuditDays), r.owner)
}

func stepAlerts(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM alert WHERE resolved_at IS NOT NULL AND resolved_at < $1
		AND ($2::bigint IS NULL OR owner_user_id = $2)`, r.daysAgoISO(r.cfg.AlertDays), r.owner)
}

func stepRateLimitEvents(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	epoch := float64(r.now.UnixNano()) / 1e9 // time.time()
	return r.scalar(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE at < $1
		AND (substr(scope, 1, 6) <> 'havel_' OR at < $2)`,
		epoch-float64(r.cfg.RateLimitHours*3600), epoch-float64(havelLimitDays*86400))
}

func stepHavelGap(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	return r.scalar(ctx, `SELECT COUNT(*) FROM havel_gap WHERE created_at < $1`, isoDate(r.daysAgo(havelGapDays)))
}

// stepLoginTokens is login_link.purge (global run only).
func stepLoginTokens(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	return r.scalar(ctx, `SELECT COUNT(*) FROM login_token WHERE expires_at < $1`, pyISO(r.now.Add(-24*time.Hour)))
}

// stepWebauthnChallenges is passkeys.purge (global run only). Its cutoff keeps
// the microseconds, as passkeys._iso does.
func stepWebauthnChallenges(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	return r.scalar(ctx, `SELECT COUNT(*) FROM webauthn_challenge WHERE expires_at < $1`,
		pyISOMicro(r.now.Add(-24*time.Hour)))
}

func stepDoorCodePins(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	return r.scalar(ctx, `SELECT COUNT(*) FROM door_code WHERE pin_enc IS NOT NULL
		AND valid_to IS NOT NULL AND valid_to < $1`, r.daysAgoISO(1))
}

// stepCleaning is cleaning.purge.
func stepCleaning(ctx context.Context, r *runner) (int, error) {
	cutoff := isoDate(r.daysAgo(cleaningDays))
	notes, err := r.scalar(ctx, `SELECT COUNT(*) FROM cleaning_event WHERE notes_enc IS NOT NULL
		AND scheduled_date < $1
		AND apartment_id IN (SELECT a.id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`,
		cutoff, r.owner)
	if err != nil {
		return 0, err
	}
	shares, err := r.scalar(ctx, `SELECT COUNT(*) FROM cleaning_share WHERE expires_at < $1
		AND ($2::bigint IS NULL OR owner_user_id = $2)`, cutoff, r.owner)
	if err != nil {
		return 0, err
	}
	return notes + shares, nil
}

// stepPush is push.purge (owner-scoped runs included).
func stepPush(ctx context.Context, r *runner) (int, error) {
	scope := ` AND ($2::bigint IS NULL OR user_account_id = $2)`
	alerts, err := r.scalar(ctx, `SELECT COUNT(*) FROM push_outbox WHERE created_at < $1`+scope,
		pyISO(r.now.AddDate(0, 0, -pushOutboxKeepDays)), r.owner)
	if err != nil {
		return 0, err
	}
	devices, err := r.ids(ctx, `SELECT id FROM push_subscription WHERE last_seen_at < $1`+scope+` ORDER BY id`,
		pyISO(r.now.AddDate(0, 0, -pushUnseenDays)), r.owner)
	if err != nil {
		return 0, err
	}
	return alerts + len(devices), nil
}

// stepGuideImports is guest_guide_import.purge (global run only).
func stepGuideImports(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	stale, err := r.scalar(ctx, `SELECT COUNT(*) FROM guide_import WHERE raw_json IS NOT NULL AND created_at < $1`,
		isoDate(r.daysAgo(guideRawDays)))
	if err != nil {
		return 0, err
	}
	old, err := r.scalar(ctx, `SELECT COUNT(*) FROM guide_import WHERE status = 'failed' AND created_at < $1`,
		isoDate(r.daysAgo(guideRowDays)))
	if err != nil {
		return 0, err
	}
	return stale + old, nil
}

// stepGuestChats is leon.purge.
func stepGuestChats(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM (SELECT c.id FROM guest_chat c JOIN apartment a ON a.id = c.apartment_id
		LEFT JOIN reservation r ON r.id = c.reservation_id
		WHERE ($1::bigint IS NULL OR a.owner_user_id = $1) AND ((c.door = 'stay' AND (r.id IS NULL OR r.date_to < $2))
		OR (c.door = 'qr' AND substr(c.last_message_at, 1, 10) < $2))) x`,
		r.owner, isoDate(r.daysAgo(leonRetentionDays)))
}

func stepLegalAcceptance(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM legal_acceptance WHERE user_account_id IN (SELECT id FROM user_account
		WHERE active = 0 AND last_login_at IS NOT NULL AND last_login_at < $1)
		AND ($2::bigint IS NULL OR user_account_id = $2)`, r.daysAgoISO(r.cfg.AuditDays), r.owner)
}

// stepWorkspaces is retention._workspace_deletion_step in a dry run (global
// run only): workspaces whose deletion date has passed.
func stepWorkspaces(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	return r.scalar(ctx, `SELECT COUNT(*) FROM user_account
		WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= $1`, pyISO(r.now))
}
