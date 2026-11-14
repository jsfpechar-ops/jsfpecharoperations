package onboarding

// The try-it "Delete and continue" button (brief 1603): demo.delete_demo_stay
// (App/app/demo.py 126-144). It deletes one demo stay of the property and its
// made-up guests, and never touches a real stay.

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
)

// wizardDeleteDemoStay is delete_demo_stay(stay, apartment): false when the
// stay is not this property's or its source is not "demo". The passport photo
// files of the guests go first (needs a writable UBYHOST_DATA_DIR volume, brief
// 1640), as in Python; the alerts, guests and the stay then go in one
// transaction. A file that cannot be removed fails the call and leaves every row.
func (s *wizardServer) wizardDeleteDemoStay(ctx context.Context, apartmentID, stayID int64) (bool, error) {
	var source string
	err := s.pool.QueryRow(ctx, `SELECT COALESCE(source, '') FROM reservation WHERE id = $1 AND apartment_id = $2`,
		stayID, apartmentID).Scan(&source)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if source != "demo" {
		return false, nil
	}
	guestIDs, err := demoIDs(ctx, s.pool, `SELECT id FROM guest WHERE reservation_id = $1 ORDER BY id`, stayID)
	if err != nil {
		return false, err
	}
	if len(guestIDs) > 0 {
		dataDir := s.getenv("UBYHOST_DATA_DIR")
		if dataDir == "" {
			return false, errDemoDataDir
		}
		for _, id := range guestIDs {
			if err := demoDeletePhoto(dataDir, id); err != nil {
				return false, err
			}
		}
	}
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer tx.Rollback(ctx) //nolint:errcheck // no-op after a successful commit
	for _, sql := range []string{
		`DELETE FROM alert WHERE reservation_id = $1`,
		`DELETE FROM guest WHERE reservation_id = $1`,
		`DELETE FROM reservation WHERE id = $1 AND source = 'demo'`,
	} {
		if _, err := tx.Exec(ctx, sql, stayID); err != nil {
			return false, err
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return false, err
	}
	return true, nil
}
