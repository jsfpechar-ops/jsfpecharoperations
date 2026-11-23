package retention

import (
	"context"
	"fmt"
	"log/slog"
	"os"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/welcomeback"
)

func (r *runner) getenv() func(string) string {
	if r.cfg.Getenv != nil {
		return r.cfg.Getenv
	}
	return os.Getenv
}

// stepWorkspaces is retention._workspace_deletion_step (global run only).
func stepWorkspaces(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	now := pyISO(r.now)
	due, err := r.scalar(ctx, `SELECT COUNT(*) FROM user_account
		WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= $1`, now)
	if err != nil {
		return 0, err
	}
	if r.dry {
		return due, nil
	}
	if err := workspaceDeletionReminders(ctx, r); err != nil {
		return 0, err
	}
	if due == 0 {
		return 0, nil
	}
	ids, err := r.ids(ctx, `SELECT id FROM user_account
		WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= $1 ORDER BY id`, now)
	if err != nil {
		return 0, err
	}
	for _, ownerID := range ids {
		guestIDs, err := deleteWorkspace(ctx, r, ownerID)
		if err != nil {
			return 0, err
		}
		deleteWorkspaceGuestPhotos(r.cfg.DataDir, guestIDs)
	}
	return due, nil
}

// workspaceDeletionReminders is retention._workspace_deletion_reminders.
func workspaceDeletionReminders(ctx context.Context, r *runner) error {
	now := pyISO(r.now)
	soon := pyISO(r.now.AddDate(0, 0, workspaceReminderDays))
	rows, err := r.pool.Query(ctx, `SELECT id, deletion_due_at FROM user_account
		WHERE deletion_due_at IS NOT NULL AND deletion_due_at > $1 AND deletion_due_at <= $2
		ORDER BY id`, now, soon)
	if err != nil {
		return err
	}
	defer rows.Close()
	getenv := r.getenv()
	for rows.Next() {
		var id int64
		var due string
		if err := rows.Scan(&id, &due); err != nil {
			return err
		}
		if _, err := mail.QueueWorkspaceDeletion(ctx, r.pool, getenv, id, due, mail.DeletionWeekBefore, r.now); err != nil {
			return err
		}
	}
	return rows.Err()
}

// deleteWorkspace is retention._delete_workspace (database half). It returns
// guest ids whose passport photos are removed after the transaction commits.
func deleteWorkspace(ctx context.Context, r *runner, ownerID int64) ([]int64, error) {
	var guestIDs []int64
	err := pgx.BeginFunc(ctx, r.pool, func(tx pgx.Tx) error {
		rows, err := tx.Query(ctx, `SELECT g.id FROM guest g
			JOIN reservation r ON r.id = g.reservation_id
			JOIN apartment a ON a.id = r.apartment_id
			WHERE a.owner_user_id = $1`, ownerID)
		if err != nil {
			return err
		}
		guestIDs, err = pgx.CollectRows(rows, pgx.RowTo[int64])
		if err != nil {
			return err
		}
		apt := `(SELECT id FROM apartment WHERE owner_user_id = $1)`
		steps := []struct {
			sql  string
			args []any
		}{
			{`DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id IN ` + apt + `)`, []any{ownerID}},
			{`DELETE FROM guest_form_draft WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id IN ` + apt + `)`, []any{ownerID}},
			{`DELETE FROM submission WHERE apartment_id IN ` + apt, []any{ownerID}},
			{`DELETE FROM door_code WHERE apartment_id IN ` + apt, []any{ownerID}},
			{`DELETE FROM reservation WHERE apartment_id IN ` + apt, []any{ownerID}},
			{`DELETE FROM stay_fee_adjustment WHERE apartment_id IN ` + apt, []any{ownerID}},
			{`DELETE FROM stay_fee_filing WHERE apartment_id IN ` + apt, []any{ownerID}},
			{`INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1')
				ON CONFLICT (key) DO UPDATE SET value = '1'`, nil},
			{`DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE owner_user_id = $1)`, []any{ownerID}},
			{`DELETE FROM invoice WHERE owner_user_id = $1 AND corrects_invoice_id IS NOT NULL`, []any{ownerID}},
			{`DELETE FROM invoice WHERE owner_user_id = $1`, []any{ownerID}},
			{`UPDATE settings SET value = '' WHERE key = 'invoice_purge_unlock'`, nil},
			{`DELETE FROM email_outbox WHERE owner_user_id = $1 OR apartment_id IN ` + apt, []any{ownerID, ownerID}},
			{`DELETE FROM apartment_slug WHERE apartment_id IN ` + apt, []any{ownerID}},
			{`DELETE FROM apartment WHERE owner_user_id = $1`, []any{ownerID}},
			{`DELETE FROM invoice_sequence WHERE legal_entity_id IN (SELECT id FROM legal_entity WHERE owner_user_id = $1)`, []any{ownerID}},
			{`DELETE FROM legal_entity WHERE owner_user_id = $1`, []any{ownerID}},
			{`DELETE FROM data_subject_request WHERE owner_user_id = $1`, []any{ownerID}},
			{`DELETE FROM alert WHERE owner_user_id = $1`, []any{ownerID}},
			{`DELETE FROM legal_acceptance WHERE user_account_id = $1`, []any{ownerID}},
			{`DELETE FROM lifecycle_mail_sent WHERE user_account_id = $1`, []any{ownerID}},
			{`DELETE FROM ad_click WHERE user_account_id = $1`, []any{ownerID}},
			{`DELETE FROM login_token WHERE user_account_id = $1`, []any{ownerID}},
			{`DELETE FROM passkey WHERE user_account_id = $1`, []any{ownerID}},
			{`DELETE FROM webauthn_challenge WHERE user_account_id = $1`, []any{ownerID}},
			{`DELETE FROM push_outbox WHERE user_account_id = $1`, []any{ownerID}},
			{`DELETE FROM push_subscription WHERE user_account_id = $1`, []any{ownerID}},
			{`DELETE FROM lock_account WHERE owner_user_id = $1`, []any{ownerID}},
			{`DELETE FROM billing_account WHERE owner_user_id = $1`, []any{ownerID}},
			{`DELETE FROM billing_month_snapshot WHERE owner_user_id = $1`, []any{ownerID}},
			{`DELETE FROM payment_request WHERE owner_user_id = $1`, []any{ownerID}},
			{`DELETE FROM stripe_account WHERE owner_user_id = $1`, []any{ownerID}},
		}
		for _, step := range steps {
			if _, err := tx.Exec(ctx, step.sql, step.args...); err != nil {
				return err
			}
		}
		for _, table := range []string{"property_page", "property_slug", "property_slug_history", "booking_hold"} {
			q := fmt.Sprintf(`DELETE FROM %s WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = $1)`, table)
			if _, err := tx.Exec(ctx, q, ownerID); err != nil {
				return err
			}
		}
		if _, err := tx.Exec(ctx, `UPDATE platform_invoice SET owner_user_id = NULL WHERE owner_user_id = $1`, ownerID); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `UPDATE founder_slot SET owner_user_id = NULL WHERE owner_user_id = $1`, ownerID); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `DELETE FROM audit WHERE owner_user_id = $1`, ownerID); err != nil {
			return err
		}
		if err := welcomeback.Forget(ctx, tx, ownerID); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `DELETE FROM user_account WHERE id = $1`, ownerID); err != nil {
			return err
		}
		return nil
	})
	return guestIDs, err
}

// deleteWorkspaceGuestPhotos is the file half of _delete_workspace: one failing
// file must not stop the rest (Python logs.exception and continues).
func deleteWorkspaceGuestPhotos(dataDir string, guestIDs []int64) {
	if dataDir == "" || len(guestIDs) == 0 {
		return
	}
	for _, id := range guestIDs {
		if err := deletePhoto(dataDir, id); err != nil {
			slog.Error("workspace deletion: guest photo not removed", "guest_id", id, "err", err)
		}
	}
}
