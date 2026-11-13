# 1211 appendix: file contents

Read by the extractor of [the brief](../1211-go-retention-apply.md); do not retype. Deleted in the report step.

<!-- file: /tmp/1211-retention.patch -->
````diff
diff --git a/go/internal/retention/retention.go b/go/internal/retention/retention.go
index 58a9fd4..25b896e 100644
--- a/go/internal/retention/retention.go
+++ b/go/internal/retention/retention.go
@@ -35,9 +35,6 @@ const (
 	leonRetentionDays      = 30  // leon.RETENTION_DAYS
 )
 
-// errApplyNotPorted fails a run with both apply switches on: this build only counts.
-var errApplyNotPorted = errors.New("retention: deleting is not ported to Go yet (brief 1211); nothing deleted")
-
 // Config holds the switches and windows the Python job reads from config.py.
 type Config struct {
 	DryRun         bool
@@ -163,10 +160,6 @@ func Run(ctx context.Context, pool *pgxpool.Pool, cfg Config, today, now time.Ti
 		dry:   cfg.DryRun,
 	}
 	sum := Summary{DryRun: r.dry, OwnerUserID: owner, Counts: []Count{}}
-	if !r.dry {
-		// Brief 1211 adds the deleting half; until then Go only counts.
-		return sum, errApplyNotPorted
-	}
 	var first error
 	cut := r.cutoffs()
 	for _, s := range steps {
````

<!-- file: go/internal/retention/steps.go -->
````go
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
````

<!-- file: go/internal/retention/golden_test.go -->
````go
package retention

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// golden is testdata/golden.json, written by App/scripts/retention_golden.py
// from the real Python retention.run() on the same fixture.
type golden struct {
	Today     string            `json:"today"`
	Now       string            `json:"now"`
	Photos    []string          `json:"photos"`
	Queries   map[string]string `json:"queries"`
	Scenarios []struct {
		Name   string              `json:"name"`
		Owner  *int64              `json:"owner_user_id"`
		DryRun bool                `json:"dry_run"`
		Error  *string             `json:"error"`
		Counts [][2]any            `json:"counts"`
		Photos []string            `json:"photos"`
		State  map[string][]string `json:"state"`
	} `json:"scenarios"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

// TestRunMatchesPythonGolden replays every scenario of golden.json: same
// fixture, same instant, same switches; counts, first failure, every touched
// table and the photo directory must match Python.
func TestRunMatchesPythonGolden(t *testing.T) {
	g := loadGolden(t)
	today, err := time.Parse("2006-01-02", g.Today)
	if err != nil {
		t.Fatal(err)
	}
	now, err := time.Parse("2006-01-02T15:04:05.000000Z", g.Now)
	if err != nil {
		t.Fatal(err)
	}
	fixture, err := os.ReadFile("testdata/fixture.sql")
	if err != nil {
		t.Fatal(err)
	}
	if len(g.Scenarios) != 4 {
		t.Fatalf("golden has %d scenarios, want 4", len(g.Scenarios))
	}
	for _, sc := range g.Scenarios {
		t.Run(sc.Name, func(t *testing.T) {
			pool := testPool(t)
			ctx := context.Background()
			if _, err := pool.Exec(ctx, string(fixture)); err != nil {
				t.Fatal(err)
			}
			dataDir := t.TempDir()
			photos := filepath.Join(dataDir, "passport_photos")
			if err := os.MkdirAll(photos, 0o700); err != nil {
				t.Fatal(err)
			}
			for _, p := range g.Photos {
				if err := os.WriteFile(filepath.Join(photos, p), []byte("x"), 0o600); err != nil {
					t.Fatal(err)
				}
			}
			cfg := Config{DryRun: sc.DryRun, AuditDays: 1095, AlertDays: 365, RateLimitHours: 24, NoticeDays: 30, DataDir: dataDir}
			sum, err := Run(ctx, pool, cfg, today, now, sc.Owner)
			switch {
			case sc.Error == nil && err != nil:
				t.Fatalf("Run: %v, Python had no error", err)
			case sc.Error != nil && *sc.Error == "workspaces" && !errors.Is(err, ErrWorkspacesNotPorted):
				t.Fatalf("Run error %v, want ErrWorkspacesNotPorted", err)
			case sc.Error != nil && *sc.Error != "workspaces":
				t.Fatalf("golden records Python error %s", *sc.Error)
			}
			var want, got []string
			for _, c := range sc.Counts {
				want = append(want, fmt.Sprintf("%v=%v", c[0], c[1]))
			}
			for _, c := range sum.Counts {
				got = append(got, fmt.Sprintf("%s=%d", c.Name, c.Count))
			}
			if !reflect.DeepEqual(got, want) {
				t.Errorf("counts\n got %v\nwant %v", got, want)
			}
			names := make([]string, 0, len(g.Queries))
			for k := range g.Queries {
				names = append(names, k)
			}
			sort.Strings(names)
			for _, name := range names {
				rows, err := pool.Query(ctx, g.Queries[name])
				if err != nil {
					t.Fatalf("%s: %v", name, err)
				}
				gotRows, err := pgx.CollectRows(rows, pgx.RowTo[string])
				if err != nil {
					t.Fatalf("%s: %v", name, err)
				}
				wantRows := sc.State[name]
				if wantRows == nil {
					wantRows = []string{}
				}
				if gotRows == nil {
					gotRows = []string{}
				}
				if !reflect.DeepEqual(gotRows, wantRows) {
					t.Errorf("%s\n got %s\nwant %s", name, strings.Join(gotRows, "\n     "), strings.Join(wantRows, "\n     "))
				}
			}
			entries, err := os.ReadDir(photos)
			if err != nil {
				t.Fatal(err)
			}
			left := []string{}
			for _, e := range entries {
				left = append(left, e.Name())
			}
			sort.Strings(left)
			if !reflect.DeepEqual(left, sc.Photos) {
				t.Errorf("photos left %v, want %v", left, sc.Photos)
			}
		})
	}
}

// TestApplyWithoutDataDirDeletesNoGuest: with UBYHOST_DATA_DIR unset the
// guest step fails before any row or file goes; the other steps still run.
func TestApplyWithoutDataDirDeletesNoGuest(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	fixture, err := os.ReadFile("testdata/fixture.sql")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, string(fixture)); err != nil {
		t.Fatal(err)
	}
	owner := int64(1)
	cfg := Config{AuditDays: 1095, AlertDays: 365, RateLimitHours: 24, NoticeDays: 30}
	now := time.Date(2026, 1, 20, 3, 0, 0, 0, time.UTC)
	sum, err := Run(ctx, pool, cfg, now, now, &owner)
	if err == nil || !strings.Contains(err.Error(), "UBYHOST_DATA_DIR") {
		t.Fatalf("Run error %v, want the data dir error", err)
	}
	var n int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM guest`).Scan(&n); err != nil || n != 10 {
		t.Fatalf("guests left %d (%v), want 10", n, err)
	}
	if len(sum.Counts) == 0 || sum.Counts[0].Name != "invoices" {
		t.Fatalf("counts %v: guests must be missing, invoices first", sum.Counts)
	}
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops the database at the end.
// It skips when the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_retention_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}
````

<!-- file: App/scripts/retention_golden.py -->
````python
"""Write go/internal/retention/testdata/golden.json from the real Python retention job.

Needs a disposable PostgreSQL server (the Go port runs on PostgreSQL only).
Run from App/ with the venv (create it first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/var/tmp/pg&port=5433' \
        .venv/bin/python scripts/retention_golden.py [--check]

The script creates its own database (ubyhost_retention_golden_<pid>) on that
server and drops it at the end. For each scenario it rebuilds the schema from
App/migrations_pg, loads go/internal/retention/testdata/fixture.sql, creates
the photo files, runs retention.run() at a frozen instant and records the
counts, the first failure and the state of every table the job touches.
--check compares with the committed file instead of writing it (exit 1 on a
difference). The Go test in go/internal/retention/ replays the same scenarios.

One deliberate difference: the Go port does not send the workspace-deletion
reminder mail or delete workspaces, so outside a dry run its workspaces step
fails closed when there is anything to do. This script patches the Python
step the same way (go_workspaces_step below); everything else is unpatched.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
PKG = REPO / "go" / "internal" / "retention" / "testdata"
OUT = PKG / "golden.json"
FIXTURE = PKG / "fixture.sql"

TODAY = date(2026, 1, 20)
NOW = datetime(2026, 1, 20, 3, 0, 0, 250000, tzinfo=UTC)
PHOTOS = ["1000.jpg.enc", "1001.png", "1002.jpg", "2000.pdf.enc", "notes.txt"]
SCENARIOS = [
    ("global_dry", None, True),
    ("owner1_dry", 1, True),
    ("owner1_apply", 1, False),
    ("global_apply", None, False),
]
# One text column per row, so Go and Python compare plain strings.
QUERIES = {
    "guest": "SELECT id::text || '|' || COALESCE(filled_ip, '~') FROM guest ORDER BY id",
    "submission": "SELECT id::text FROM submission ORDER BY id",
    "reservation": (
        "SELECT id::text || '|' || COALESCE(guest_email, '~') || '|' || COALESCE(phone_last4, '~')"
        " || '|' || updated_at FROM reservation ORDER BY id"
    ),
    "reservation_claim": (
        "SELECT reservation_id::text || '|' || COALESCE(email, '~') || '|' || updated_at"
        " FROM reservation_claim ORDER BY reservation_id"
    ),
    "stay_fee_filing": "SELECT id::text FROM stay_fee_filing ORDER BY id",
    "stay_fee_adjustment": "SELECT id::text FROM stay_fee_adjustment ORDER BY id",
    "invoice": "SELECT id::text FROM invoice ORDER BY id",
    "invoice_item": "SELECT id::text FROM invoice_item ORDER BY id",
    "platform_invoice": "SELECT id::text FROM platform_invoice ORDER BY id",
    "bank_payment": "SELECT bank_tx_id FROM bank_payment ORDER BY bank_tx_id",
    "audit": (
        "SELECT id::text || '|' || at || '|' || COALESCE(actor, '~') || '|' || action || '|'"
        " || COALESCE(detail, '~') || '|' || COALESCE(owner_user_id::text, '~')"
        " || '|' || COALESCE(actor_user_id::text, '~') || '|' || COALESCE(impersonator_user_id::text, '~')"
        " FROM audit ORDER BY id"
    ),
    "alert": (
        "SELECT id::text || '|' || level || '|' || kind || '|' || COALESCE(owner_user_id::text, '~') || '|'"
        " || COALESCE(apartment_id::text, '~') || '|' || COALESCE(reservation_id::text, '~') || '|'"
        " || COALESCE(dedupe_key, '~') || '|' || message || '|' || COALESCE(detail, '~') || '|'"
        " || COALESCE(params, '~') || '|' || created_at || '|' || COALESCE(resolved_at, '~')"
        " FROM alert ORDER BY id"
    ),
    "rate_limit_event": "SELECT id::text FROM rate_limit_event ORDER BY id",
    "havel_gap": "SELECT id::text FROM havel_gap ORDER BY id",
    "login_token": "SELECT id::text FROM login_token ORDER BY id",
    "webauthn_challenge": "SELECT id::text FROM webauthn_challenge ORDER BY id",
    "door_code": (
        "SELECT id::text || '|' || COALESCE(pin_enc, '~') || '|' || updated_at FROM door_code ORDER BY id"
    ),
    "cleaning_event": "SELECT id::text || '|' || COALESCE(notes_enc, '~') FROM cleaning_event ORDER BY id",
    "cleaning_share": "SELECT id::text FROM cleaning_share ORDER BY id",
    "push_outbox": "SELECT id::text FROM push_outbox ORDER BY id",
    "push_subscription": "SELECT id::text FROM push_subscription ORDER BY id",
    "guide_import": (
        "SELECT id::text || '|' || status || '|' || COALESCE(raw_json, '~') FROM guide_import ORDER BY id"
    ),
    "guest_chat": "SELECT id::text FROM guest_chat ORDER BY id",
    "guest_chat_message": "SELECT id::text FROM guest_chat_message ORDER BY id",
    "guest_question": "SELECT id::text FROM guest_question ORDER BY id",
    "legal_acceptance": "SELECT id::text FROM legal_acceptance ORDER BY id",
    "user_account": "SELECT id::text FROM user_account ORDER BY id",
    "settings": "SELECT key || '=' || COALESCE(value, '~') FROM settings ORDER BY key",
    "email_outbox": "SELECT COUNT(*)::text FROM email_outbox",
}
RETENTION_ENV = (
    "UBYHOST_RETENTION_AUTOPURGE",
    "UBYHOST_RETENTION_NOTICE_DAYS",
    "UBYHOST_AUDIT_RETENTION_DAYS",
    "UBYHOST_ALERT_RETENTION_DAYS",
    "UBYHOST_RATE_LIMIT_RETENTION_HOURS",
)


class WorkspacesNotPorted(RuntimeError):
    """The Go port's fail-closed workspaces step, mirrored here."""


def _url_for(base: str, name: str) -> str:
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))


def _migrations_sql() -> list[str]:
    out = []
    for path in sorted((APP / "migrations_pg").glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        i = text.find("-- +goose Up")
        if i >= 0:
            text = text[i + len("-- +goose Up"):]
        j = text.find("-- +goose Down")
        if j >= 0:
            text = text[:j]
        out.append(text)
    return out


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.astimezone().replace(tzinfo=None)


def _freeze() -> None:
    from app import db, login_link, passkeys, push, retention

    db.datetime = _Frozen
    retention.datetime = _Frozen
    retention.time = SimpleNamespace(time=lambda: NOW.timestamp(), perf_counter=time.perf_counter)
    for module in (login_link, passkeys, push):
        module._now = lambda: NOW


def _patch_workspaces() -> None:
    from app import db, retention

    original = dict(retention.STEPS)["workspaces"]

    def go_workspaces_step(today, dry_run, owner_user_id):
        if owner_user_id is not None or dry_run:
            return original(today, dry_run, owner_user_id)
        now = db.utcnow()
        soon = (NOW + timedelta(days=retention.WORKSPACE_REMINDER_DAYS)).replace(microsecond=0).isoformat()
        due = db.query_one(
            "SELECT COUNT(*) AS n FROM user_account WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= ?",
            (now,),
        )["n"]
        reminders = db.query_one(
            "SELECT COUNT(*) AS n FROM user_account WHERE deletion_due_at IS NOT NULL "
            "AND deletion_due_at > ? AND deletion_due_at <= ?",
            (now, soon),
        )["n"]
        if due or reminders:
            raise WorkspacesNotPorted(f"due {due}, reminders {reminders}")
        return 0

    retention.STEPS[:] = [
        (name, go_workspaces_step if name == "workspaces" else fn) for name, fn in retention.STEPS
    ]


def _scenario(psycopg, url: str, photos_dir: Path, name: str, owner, dry_run: bool) -> dict:
    from app import db, retention

    db.close_connections()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        for sql in _migrations_sql():
            conn.execute(sql)
        conn.execute(FIXTURE.read_text(encoding="utf-8"))
    photos_dir.mkdir(parents=True, exist_ok=True)
    for old in photos_dir.iterdir():
        old.unlink()
    for photo in PHOTOS:
        (photos_dir / photo).write_bytes(b"x")
    error = None
    try:
        retention.run(TODAY, dry_run=dry_run, owner_user_id=owner)
    except WorkspacesNotPorted:
        error = "workspaces"
    except Exception as exc:  # noqa: BLE001 - recorded; the Go test must fail the same way
        error = type(exc).__name__
    db.close_connections()
    state = {}
    with psycopg.connect(url, autocommit=True) as conn:
        for key, sql in QUERIES.items():
            state[key] = [row[0] for row in conn.execute(sql).fetchall()]
        last = conn.execute("SELECT value FROM settings WHERE key = 'retention_last_run'").fetchone()[0]
    counts = [[k, v] for k, v in json.loads(last)["counts"].items()]
    return {
        "name": name,
        "owner_user_id": owner,
        "dry_run": dry_run,
        "error": error,
        "counts": counts,
        "photos": sorted(p.name for p in photos_dir.iterdir()),
        "state": state,
    }


def render() -> str:
    base = os.environ.get("UBYHOST_TEST_DATABASE_URL") or os.environ.get("UBYHOST_DATABASE_URL")
    if not base:
        raise SystemExit("set UBYHOST_TEST_DATABASE_URL to a disposable PostgreSQL server")
    import psycopg

    name = f"ubyhost_retention_golden_{os.getpid()}"
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = _url_for(base, name)
    data_dir = Path(tempfile.mkdtemp(prefix="ubyhost-retention-golden-"))
    os.environ.pop("UBYHOST_DB", None)
    for key in RETENTION_ENV:
        os.environ.pop(key, None)
    os.environ["UBYHOST_DATABASE_URL"] = url
    os.environ["UBYHOST_DATA_DIR"] = str(data_dir)
    os.environ.setdefault("UBYHOST_SECRET_KEY", "retention-golden-not-a-secret")
    os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
    sys.path.insert(0, str(APP))
    try:
        _freeze()
        _patch_workspaces()
        scenarios = [
            _scenario(psycopg, url, data_dir / "passport_photos", n, owner, dry)
            for n, owner, dry in SCENARIOS
        ]
    finally:
        from app import db

        db.close_connections()
        with psycopg.connect(base, autocommit=True) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
    doc = {
        "today": TODAY.isoformat(),
        "now": NOW.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "photos": PHOTOS,
        "patched": "workspaces: outside a dry run fails closed when a workspace is due or a reminder is due",
        "queries": QUERIES,
        "scenarios": scenarios,
    }
    return json.dumps(doc, indent=1, ensure_ascii=True) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv[1:]:
        if OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT} is out of date: rerun scripts/retention_golden.py")
            raise SystemExit(1)
        print("golden up to date")
    else:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT}")
````

<!-- file: App/tests/test_go_retention_parity.py -->
````python
"""The Go retention job (go/internal/retention) replays golden.json, which
scripts/retention_golden.py writes from the real Python retention.run().

On PostgreSQL (UBYHOST_TEST_DATABASE_URL or UBYHOST_DATABASE_URL set, as in
the test-postgres-full CI row) this regenerates the golden in a throwaway
database and fails if the committed file is out of date: a change to
App/app/retention.py or a helper it calls must come with a new golden (and a
matching Go change). If this fails, rerun from App/:

    UBYHOST_TEST_DATABASE_URL=<disposable server> .venv/bin/python scripts/retention_golden.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "retention" / "testdata" / "golden.json"
SCRIPT = APP_DIR / "scripts" / "retention_golden.py"
PG_URL = os.environ.get("UBYHOST_TEST_DATABASE_URL") or os.environ.get("UBYHOST_DATABASE_URL")


def test_golden_lists_four_scenarios_and_the_script_queries():
    doc = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert [s["name"] for s in doc["scenarios"]] == ["global_dry", "owner1_dry", "owner1_apply", "global_apply"]
    assert '"queries": ' in GOLDEN.read_text(encoding="utf-8")
    assert all(s["error"] in (None, "workspaces") for s in doc["scenarios"])


@pytest.mark.skipif(not PG_URL, reason="needs PostgreSQL (UBYHOST_TEST_DATABASE_URL or UBYHOST_DATABASE_URL)")
def test_golden_is_up_to_date_with_python_retention():
    env = {k: v for k, v in os.environ.items() if k not in ("UBYHOST_DB",)}
    env["UBYHOST_TEST_DATABASE_URL"] = PG_URL
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=str(APP_DIR),
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]
    assert "golden up to date" in result.stdout
````
