package doorcleaning

import (
	"context"
	"crypto/subtle"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"
)

// activation is the apartment row that cleaning_codes._activate reads (a join of
// cleaning_property and apartment). Nullable columns are pointers.
type activation struct {
	CodeID        *int64
	PendingCodeID *int64
	Active        int64
	ArchivedAt    *string
	LockID        *string
	LockProvider  *string
	OwnerUserID   *int64
}

// activate is cleaning_codes._activate(cur, row): make row the property's active code, after
// checking that a TTLock code still belongs to the apartment's current binding. It runs inside
// the caller's transaction and never contacts the provider. The previous active code is
// revoked (ttlock) or revoked/detached (manual) unless it is the same physical PIN.
func (q *queue) activate(ctx context.Context, tx pgx.Tx, row codeRow, now string) error {
	var cur activation
	hasCurrent := true
	err := tx.QueryRow(ctx,
		"SELECT p.code_id, p.pending_code_id, a.active, a.archived_at, a.lock_id, a.lock_provider, a.owner_user_id "+
			"FROM cleaning_property p JOIN apartment a ON a.id = p.apartment_id WHERE p.apartment_id = $1",
		row.ApartmentID).Scan(&cur.CodeID, &cur.PendingCodeID, &cur.Active, &cur.ArchivedAt,
		&cur.LockID, &cur.LockProvider, &cur.OwnerUserID)
	if errNoRow(err) {
		hasCurrent = false
	} else if err != nil {
		return err
	}

	managed, err := q.codeByID(ctx, tx, row.ID)
	if err != nil {
		return err
	}
	if managed.Source == "ttlock" {
		var accountOwner *int64
		accountFound := false
		if managed.LockAccountID != nil {
			err := tx.QueryRow(ctx, "SELECT owner_user_id FROM lock_account WHERE id = $1",
				*managed.LockAccountID).Scan(&accountOwner)
			if err != nil && !errNoRow(err) {
				return err
			}
			accountFound = err == nil
		}
		bound := hasCurrent && cur.Active != 0 &&
			(cur.ArchivedAt == nil || *cur.ArchivedAt == "") &&
			cur.PendingCodeID != nil && *cur.PendingCodeID == row.ID &&
			derefStr(cur.LockProvider) == "ttlock" &&
			cur.LockID != nil && managed.LockID != nil && *cur.LockID == *managed.LockID &&
			accountFound && accountOwner != nil && cur.OwnerUserID != nil && *accountOwner == *cur.OwnerUserID
		if !bound {
			if _, err := tx.Exec(ctx,
				"UPDATE cleaning_code SET state = 'revoke_pending', attempts = 0, next_attempt_at = $1, "+
					"claimed_at = NULL, updated_at = $1 WHERE id = $2", now, row.ID); err != nil {
				return err
			}
			_, err := tx.Exec(ctx,
				"UPDATE cleaning_property SET pending_code_id = NULL WHERE pending_code_id = $1", row.ID)
			return err
		}
	}

	if _, err := tx.Exec(ctx,
		"UPDATE cleaning_property SET code_id = $1, pending_code_id = NULL, updated_at = $2 WHERE apartment_id = $3",
		row.ID, now, row.ApartmentID); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx,
		"UPDATE cleaning_code SET state = 'active', claimed_at = NULL, updated_at = $1 WHERE id = $2",
		now, row.ID); err != nil {
		return err
	}
	if !hasCurrent || cur.CodeID == nil || *cur.CodeID == row.ID {
		return nil
	}

	previous, err := q.codeByID(ctx, tx, *cur.CodeID)
	if err != nil {
		return err
	}
	if previous.State != "active" {
		return nil
	}
	// A manual takeover of the same physical TTLock PIN must not delete it. The page shows
	// the keypad's final # for a TTLock code; it is not part of the API PIN.
	same := false
	if previous.Source == "ttlock" && managed.Source == "manual" &&
		derefStr(previous.PinEnc) != "" && derefStr(managed.PinEnc) != "" {
		prev, err := q.decrypt(previous.PinEnc)
		if err != nil {
			return err
		}
		mine, err := q.decrypt(managed.PinEnc)
		if err != nil {
			return err
		}
		same = subtle.ConstantTimeCompare([]byte(prev), []byte(strings.TrimSuffix(mine, "#"))) == 1
	}
	if same {
		_, err := tx.Exec(ctx,
			"UPDATE cleaning_code SET state = 'detached', pin_enc = NULL, updated_at = $1 WHERE id = $2",
			now, previous.ID)
		return err
	}
	_, err = tx.Exec(ctx,
		"UPDATE cleaning_code SET state = CASE WHEN source = 'ttlock' THEN 'revoke_pending' ELSE 'revoked' END, "+
			"pin_enc = CASE WHEN source = 'manual' THEN NULL ELSE pin_enc END, attempts = 0, "+
			"next_attempt_at = $1, updated_at = $1 WHERE id = $2", now, previous.ID)
	return err
}

// codeByID reads one cleaning_code row inside tx; a missing row is an error (Python would
// fail on a None row).
func (q *queue) codeByID(ctx context.Context, tx pgx.Tx, id int64) (codeRow, error) {
	c, err := scanCode(tx.QueryRow(ctx, "SELECT "+codeColumns+" FROM cleaning_code WHERE id = $1", id))
	if err != nil {
		return codeRow{}, fmt.Errorf("doorcleaning: cleaning_code %d: %w", id, err)
	}
	return c, nil
}
