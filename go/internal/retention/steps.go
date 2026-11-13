package retention

// The steps of retention.STEPS. Each returns the affected count and, outside a
// dry run, deletes or nulls exactly what it counted. SQL mirrors the Python
// statements on PostgreSQL: db.sqlite_date_expr(x) is ubyhost_sqlite_date(x),
// and "(? IS NULL OR col = ?)" is "($n::bigint IS NULL OR col = $n)".

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// ErrWorkspacesNotPorted is the fail-closed error of the workspaces step in
// apply mode: the week-before reminder mail (mail_notify.workspace_deletion)
// and the workspace delete are not ported, so Go deletes nothing there.
var ErrWorkspacesNotPorted = errors.New("retention: workspace deletion and its reminder mail are not ported to Go; nothing deleted")

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

func (r *runner) exec(ctx context.Context, sql string, args ...any) (int64, error) {
	tag, err := r.pool.Exec(ctx, sql, args...)
	if err != nil {
		return 0, err
	}
	return tag.RowsAffected(), nil
}

// --- guests: housebook.expired_guest_ids / purge_expired --------------------

const expiredGuestsSQL = `SELECT g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE COALESCE(ubyhost_sqlite_date(g.stay_to), ubyhost_sqlite_date(r.date_to)) < $1
	AND ($2::bigint IS NULL OR a.owner_user_id = $2) ORDER BY g.id`

func stepGuests(ctx context.Context, r *runner) (int, error) {
	cutoff := isoDate(housebookCutoff(r.today))
	ids, err := r.ids(ctx, expiredGuestsSQL, cutoff, r.owner)
	if err != nil || r.dry {
		return len(ids), err
	}
	if len(ids) > 0 {
		if r.cfg.DataDir == "" {
			// Without the data directory the photos cannot be found, and a row
			// deleted before its photo leaves an orphaned passport scan.
			return 0, errors.New("retention: UBYHOST_DATA_DIR is not set; no guest deleted")
		}
		// Drop the image before the row, as housebook.purge_expired does: a
		// failed file delete stops the step before any row goes.
		for _, id := range ids {
			if err := deletePhoto(r.cfg.DataDir, id); err != nil {
				return 0, err
			}
		}
		if _, err := r.exec(ctx, `DELETE FROM guest WHERE id = ANY($1)`, ids); err != nil {
			return 0, err
		}
		if err := r.audit(ctx, "retention_purge",
			fmt.Sprintf("deleted %d guest record(s) whose stay ended before %s", len(ids), cutoff), "host"); err != nil {
			return 0, err
		}
	}
	if err := r.purgeOrphanSubmissions(ctx, cutoff); err != nil {
		return 0, err
	}
	return len(ids), nil
}

// purgeOrphanSubmissions is housebook.purge_orphan_submissions.
func (r *runner) purgeOrphanSubmissions(ctx context.Context, cutoff string) error {
	ids, err := r.ids(ctx, `SELECT s.id FROM submission s JOIN apartment a ON a.id = s.apartment_id
		WHERE s.created_at < $1 AND ($2::bigint IS NULL OR a.owner_user_id = $2)
		AND NOT EXISTS (SELECT 1 FROM guest g WHERE g.submission_id = s.id OR g.receipt_submission_id = s.id)
		ORDER BY s.id`, cutoff, r.owner)
	if err != nil || len(ids) == 0 {
		return err
	}
	if _, err := r.exec(ctx, `DELETE FROM submission WHERE id = ANY($1)`, ids); err != nil {
		return err
	}
	return r.audit(ctx, "submission_orphan_purge",
		fmt.Sprintf("deleted %d submission record(s) with no surviving guest", len(ids)), "host")
}

// photoExtensions is passport_photos.ALL_EXTENSIONS (sorted).
var photoExtensions = []string{".jpg", ".pdf", ".png", ".webp"}

// deletePhoto is passport_photos.delete_photo: every encrypted and legacy
// file name the guest's photo can have under <data dir>/passport_photos.
func deletePhoto(dataDir string, guestID int64) error {
	dir := filepath.Join(dataDir, "passport_photos")
	for _, ext := range photoExtensions {
		base := strconv.FormatInt(guestID, 10) + ext
		for _, name := range []string{base + ".enc", base} {
			path := filepath.Join(dir, name)
			info, err := os.Stat(path)
			if err != nil || !info.Mode().IsRegular() {
				continue
			}
			if err := os.Remove(path); err != nil {
				return fmt.Errorf("retention: photo of guest %d not removed: %w", guestID, err)
			}
		}
	}
	return nil
}

// --- invoices: invoices.expired_ids / purge_expired --------------------------

func stepInvoices(ctx context.Context, r *runner) (int, error) {
	cutoff := isoDate(invoiceCutoff(r.today))
	ids, err := r.ids(ctx, `SELECT id FROM invoice WHERE issue_date < $1
		AND ($2::bigint IS NULL OR owner_user_id = $2)
		AND NOT EXISTS (SELECT 1 FROM invoice c WHERE c.corrects_invoice_id = invoice.id AND c.issue_date >= $1)
		ORDER BY CASE WHEN corrects_invoice_id IS NULL THEN 1 ELSE 0 END, id`, cutoff, r.owner)
	if err != nil || r.dry || len(ids) == 0 {
		return len(ids), err
	}
	if _, err := r.exec(ctx, `INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1')
		ON CONFLICT (key) DO UPDATE SET value = '1'`); err != nil {
		return 0, err
	}
	err = func() error {
		for _, id := range ids {
			if _, err := r.exec(ctx, `DELETE FROM invoice_item WHERE invoice_id = $1`, id); err != nil {
				return err
			}
			if _, err := r.exec(ctx, `DELETE FROM invoice WHERE id = $1`, id); err != nil {
				return err
			}
		}
		return nil
	}()
	// The finally block: the lock goes back on whatever happened.
	if _, lockErr := r.exec(ctx, `INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '')
		ON CONFLICT (key) DO UPDATE SET value = ''`); err == nil {
		err = lockErr
	}
	if err != nil {
		return 0, err
	}
	if err := r.audit(ctx, "invoice_retention_purge", fmt.Sprintf("deleted=%d", len(ids)), "host"); err != nil {
		return 0, err
	}
	return len(ids), nil
}

// --- platform_invoices: billing_invoices.expired_ids / purge_expired ---------

func stepPlatformInvoices(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	cutoff := isoDate(invoiceCutoff(r.today))
	ids, err := r.ids(ctx, `SELECT id FROM platform_invoice WHERE issue_date < $1
		AND NOT EXISTS (SELECT 1 FROM platform_invoice c WHERE c.corrects_id = platform_invoice.id AND c.issue_date >= $1)
		ORDER BY CASE WHEN corrects_id IS NULL THEN 1 ELSE 0 END, id`, cutoff)
	if err != nil || r.dry {
		return len(ids), err
	}
	for _, id := range ids {
		if _, err := r.exec(ctx, `DELETE FROM bank_payment WHERE matched_invoice_id = $1`, id); err != nil {
			return 0, err
		}
		if _, err := r.exec(ctx, `DELETE FROM platform_invoice WHERE id = $1`, id); err != nil {
			return 0, err
		}
	}
	payments, err := r.exec(ctx, `DELETE FROM bank_payment WHERE matched_invoice_id IS NULL AND received_on < $1`, cutoff)
	if err != nil {
		return 0, err
	}
	if len(ids) > 0 || payments > 0 {
		if err := r.audit(ctx, "platform_invoice_purge",
			fmt.Sprintf("invoices=%d payments=%d", len(ids), payments), "system"); err != nil {
			return 0, err
		}
	}
	return len(ids) + int(payments), nil
}

// --- contact minimisation ----------------------------------------------------

func stepClaimEmails(ctx context.Context, r *runner) (int, error) {
	cutoff := isoDate(r.daysAgo(claimEmailGraceDays))
	where := `email IS NOT NULL AND reservation_id IN (SELECT r.id FROM reservation r
		JOIN apartment a ON a.id = r.apartment_id
		WHERE ubyhost_sqlite_date(r.date_to) < $1 AND ($2::bigint IS NULL OR a.owner_user_id = $2))`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM reservation_claim WHERE `+where, cutoff, r.owner)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `UPDATE reservation_claim SET email = NULL, updated_at = $3 WHERE `+where,
		cutoff, r.owner, pyISO(r.now))
	return n, err
}

func stepReservationContacts(ctx context.Context, r *runner) (int, error) {
	cutoff := isoDate(r.daysAgo(claimEmailGraceDays))
	where := `(guest_email IS NOT NULL OR phone_last4 IS NOT NULL)
		AND ubyhost_sqlite_date(date_to) < $1
		AND apartment_id IN (SELECT id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM reservation WHERE `+where, cutoff, r.owner)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `UPDATE reservation SET guest_email = NULL, phone_last4 = NULL, updated_at = $3 WHERE `+where,
		cutoff, r.owner, pyISO(r.now))
	return n, err
}

func stepSubmitterIPs(ctx context.Context, r *runner) (int, error) {
	cutoff := isoDate(r.daysAgo(submitterIPGraceDays))
	where := `filled_ip IS NOT NULL
		AND COALESCE(ubyhost_sqlite_date(stay_to), (SELECT ubyhost_sqlite_date(date_to) FROM reservation r2
			WHERE r2.id = guest.reservation_id)) < $1
		AND reservation_id IN (SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id
			WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM guest WHERE `+where, cutoff, r.owner)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `UPDATE guest SET filled_ip = NULL WHERE `+where, cutoff, r.owner)
	return n, err
}

func stepEmptyReservations(ctx context.Context, r *runner) (int, error) {
	cutoff := isoDate(housebookCutoff(r.today))
	where := `ubyhost_sqlite_date(date_to) < $1
		AND NOT EXISTS (SELECT 1 FROM guest g WHERE g.reservation_id = reservation.id)
		AND apartment_id IN (SELECT id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM reservation WHERE `+where, cutoff, r.owner)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `DELETE FROM reservation WHERE `+where, cutoff, r.owner)
	return n, err
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
	if r.dry || adjustments+filings == 0 {
		return adjustments + filings, nil
	}
	// One transaction, as db.immediate(): adjustments point at their filing.
	err = pgx.BeginFunc(ctx, r.pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, `DELETE FROM stay_fee_adjustment WHERE `+where, year, r.owner); err != nil {
			return err
		}
		_, err := tx.Exec(ctx, `DELETE FROM stay_fee_filing WHERE `+where, year, r.owner)
		return err
	})
	if err != nil {
		return 0, err
	}
	return adjustments + filings, nil
}

// --- logs and evidence -------------------------------------------------------

func stepAuditRows(ctx context.Context, r *runner) (int, error) {
	cutoff := r.daysAgoISO(r.cfg.AuditDays)
	where := `at < $1 AND action NOT IN ('legal_accepted', 'door_code_terms_accepted', 'leon_terms_accepted',
		'payments_terms_accepted') AND ($2::bigint IS NULL OR owner_user_id = $2)`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM audit WHERE `+where, cutoff, r.owner)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `DELETE FROM audit WHERE `+where, cutoff, r.owner)
	return n, err
}

func stepAlerts(ctx context.Context, r *runner) (int, error) {
	cutoff := r.daysAgoISO(r.cfg.AlertDays)
	where := `resolved_at IS NOT NULL AND resolved_at < $1 AND ($2::bigint IS NULL OR owner_user_id = $2)`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM alert WHERE `+where, cutoff, r.owner)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `DELETE FROM alert WHERE `+where, cutoff, r.owner)
	return n, err
}

func stepRateLimitEvents(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	epoch := float64(r.now.UnixNano()) / 1e9 // time.time()
	cutoff := epoch - float64(r.cfg.RateLimitHours*3600)
	havel := epoch - float64(havelLimitDays*86400)
	where := `at < $1 AND (substr(scope, 1, 6) <> 'havel_' OR at < $2)`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE `+where, cutoff, havel)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `DELETE FROM rate_limit_event WHERE `+where, cutoff, havel)
	return n, err
}

func stepHavelGap(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	cutoff := isoDate(r.daysAgo(havelGapDays))
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM havel_gap WHERE created_at < $1`, cutoff)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `DELETE FROM havel_gap WHERE created_at < $1`, cutoff)
	return n, err
}

// stepLoginTokens is login_link.purge (global run only).
func stepLoginTokens(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	cutoff := pyISO(r.now.Add(-24 * time.Hour))
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM login_token WHERE expires_at < $1`, cutoff)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `DELETE FROM login_token WHERE expires_at < $1`, cutoff)
	return n, err
}

// stepWebauthnChallenges is passkeys.purge (global run only). Its cutoff keeps
// the microseconds, as passkeys._iso does.
func stepWebauthnChallenges(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	cutoff := pyISOMicro(r.now.Add(-24 * time.Hour))
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM webauthn_challenge WHERE expires_at < $1`, cutoff)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `DELETE FROM webauthn_challenge WHERE expires_at < $1`, cutoff)
	return n, err
}

func stepDoorCodePins(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	cutoff := r.daysAgoISO(1)
	where := `pin_enc IS NOT NULL AND valid_to IS NOT NULL AND valid_to < $1`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM door_code WHERE `+where, cutoff)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `UPDATE door_code SET pin_enc = NULL, updated_at = $2 WHERE `+where, cutoff, pyISO(r.now))
	return n, err
}

// stepCleaning is cleaning.purge: outside a dry run both statements run even
// when the counts are zero.
func stepCleaning(ctx context.Context, r *runner) (int, error) {
	cutoff := isoDate(r.daysAgo(cleaningDays))
	scope := `apartment_id IN (SELECT a.id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`
	notes, err := r.scalar(ctx, `SELECT COUNT(*) FROM cleaning_event WHERE notes_enc IS NOT NULL
		AND scheduled_date < $1 AND `+scope, cutoff, r.owner)
	if err != nil {
		return 0, err
	}
	shares, err := r.scalar(ctx, `SELECT COUNT(*) FROM cleaning_share WHERE expires_at < $1
		AND ($2::bigint IS NULL OR owner_user_id = $2)`, cutoff, r.owner)
	if err != nil {
		return 0, err
	}
	if !r.dry {
		if _, err := r.exec(ctx, `UPDATE cleaning_event SET notes_enc = NULL WHERE scheduled_date < $1 AND `+scope,
			cutoff, r.owner); err != nil {
			return 0, err
		}
		if _, err := r.exec(ctx, `DELETE FROM cleaning_share WHERE expires_at < $1
			AND ($2::bigint IS NULL OR owner_user_id = $2)`, cutoff, r.owner); err != nil {
			return 0, err
		}
	}
	return notes + shares, nil
}

// stepPush is push.purge (owner-scoped runs included): outside a dry run the
// outbox delete runs even when nothing is due.
func stepPush(ctx context.Context, r *runner) (int, error) {
	old := pyISO(r.now.AddDate(0, 0, -pushOutboxKeepDays))
	unseen := pyISO(r.now.AddDate(0, 0, -pushUnseenDays))
	scope := ` AND ($2::bigint IS NULL OR user_account_id = $2)`
	alerts, err := r.scalar(ctx, `SELECT COUNT(*) FROM push_outbox WHERE created_at < $1`+scope, old, r.owner)
	if err != nil {
		return 0, err
	}
	devices, err := r.ids(ctx, `SELECT id FROM push_subscription WHERE last_seen_at < $1`+scope+` ORDER BY id`, unseen, r.owner)
	if err != nil {
		return 0, err
	}
	if !r.dry {
		if _, err := r.exec(ctx, `DELETE FROM push_outbox WHERE created_at < $1`+scope, old, r.owner); err != nil {
			return 0, err
		}
		for _, id := range devices {
			if _, err := r.exec(ctx, `DELETE FROM push_outbox WHERE subscription_id = $1`, id); err != nil {
				return 0, err
			}
			if _, err := r.exec(ctx, `DELETE FROM push_subscription WHERE id = $1`, id); err != nil {
				return 0, err
			}
		}
	}
	return alerts + len(devices), nil
}

// stepGuideImports is guest_guide_import.purge (global run only).
func stepGuideImports(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	raw := isoDate(r.daysAgo(guideRawDays))
	row := isoDate(r.daysAgo(guideRowDays))
	stale, err := r.scalar(ctx, `SELECT COUNT(*) FROM guide_import WHERE raw_json IS NOT NULL AND created_at < $1`, raw)
	if err != nil {
		return 0, err
	}
	old, err := r.scalar(ctx, `SELECT COUNT(*) FROM guide_import WHERE status = 'failed' AND created_at < $1`, row)
	if err != nil {
		return 0, err
	}
	n := stale + old
	if r.dry || n == 0 {
		return n, nil
	}
	if _, err := r.exec(ctx, `UPDATE guide_import SET raw_json = NULL,
		status = CASE WHEN status = 'done' THEN 'expired' ELSE status END
		WHERE raw_json IS NOT NULL AND created_at < $1`, raw); err != nil {
		return 0, err
	}
	if _, err := r.exec(ctx, `DELETE FROM guide_import WHERE status = 'failed' AND created_at < $1`, row); err != nil {
		return 0, err
	}
	return n, nil
}

// stepGuestChats is leon.purge.
func stepGuestChats(ctx context.Context, r *runner) (int, error) {
	cutoff := isoDate(r.daysAgo(leonRetentionDays))
	chats := `SELECT c.id FROM guest_chat c JOIN apartment a ON a.id = c.apartment_id
		LEFT JOIN reservation r ON r.id = c.reservation_id
		WHERE ($1::bigint IS NULL OR a.owner_user_id = $1) AND ((c.door = 'stay' AND (r.id IS NULL OR r.date_to < $2))
		OR (c.door = 'qr' AND substr(c.last_message_at, 1, 10) < $2))`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM (`+chats+`) x`, r.owner, cutoff)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	for _, sql := range []string{
		`DELETE FROM guest_question WHERE chat_id IN (` + chats + `)`,
		`DELETE FROM guest_chat_message WHERE chat_id IN (` + chats + `)`,
		`DELETE FROM guest_chat WHERE id IN (` + chats + `)`,
	} {
		if _, err := r.exec(ctx, sql, r.owner, cutoff); err != nil {
			return 0, err
		}
	}
	return n, nil
}

func stepLegalAcceptance(ctx context.Context, r *runner) (int, error) {
	cutoff := r.daysAgoISO(r.cfg.AuditDays)
	where := `user_account_id IN (SELECT id FROM user_account WHERE active = 0
		AND last_login_at IS NOT NULL AND last_login_at < $1)
		AND ($2::bigint IS NULL OR user_account_id = $2)`
	n, err := r.scalar(ctx, `SELECT COUNT(*) FROM legal_acceptance WHERE `+where, cutoff, r.owner)
	if err != nil || r.dry || n == 0 {
		return n, err
	}
	_, err = r.exec(ctx, `DELETE FROM legal_acceptance WHERE `+where, cutoff, r.owner)
	return n, err
}

// stepWorkspaces is retention._workspace_deletion_step (global run only). The
// dry run counts exactly as Python does. Outside a dry run it fails closed
// whenever Python would queue a reminder mail or delete a workspace: neither
// is ported, so Go changes nothing and returns ErrWorkspacesNotPorted.
func stepWorkspaces(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	now := pyISO(r.now)
	due, err := r.scalar(ctx, `SELECT COUNT(*) FROM user_account
		WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= $1`, now)
	if err != nil || r.dry {
		return due, err
	}
	soon := pyISO(r.now.AddDate(0, 0, workspaceReminderDays))
	reminders, err := r.scalar(ctx, `SELECT COUNT(*) FROM user_account
		WHERE deletion_due_at IS NOT NULL AND deletion_due_at > $1 AND deletion_due_at <= $2`, now, soon)
	if err != nil {
		return 0, err
	}
	if due > 0 || reminders > 0 {
		return 0, fmt.Errorf("%w (due %d, reminders %d)", ErrWorkspacesNotPorted, due, reminders)
	}
	return 0, nil
}
