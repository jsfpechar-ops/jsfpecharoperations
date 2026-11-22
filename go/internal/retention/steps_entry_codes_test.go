package retention

import (
	"context"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

func testRunner(t *testing.T, pool *pgxpool.Pool, dry bool, owner *int64) *runner {
	t.Helper()
	now := time.Date(2026, 1, 20, 3, 0, 0, 0, time.UTC)
	return &runner{pool: pool, cfg: Config{}, today: now, now: now, owner: owner, dry: dry}
}

func testOwnerApartment(t *testing.T, ctx context.Context, pool *pgxpool.Pool) (ownerID, aptID int64) {
	t.Helper()
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, created_at)
		VALUES ('ec2032-test', 'x', '2017-01-01T00:00:00+00:00') RETURNING id`).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (internal_name, created_at, owner_user_id)
		VALUES ('EC test', '2017-01-01T00:00:00+00:00', $1) RETURNING id`, ownerID).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	return ownerID, aptID
}

func insertEntryCode(t *testing.T, ctx context.Context, pool *pgxpool.Pool, aptID int64, position int, codeType, label, enc, until string) {
	t.Helper()
	ts := "2017-01-01T00:00:00+00:00"
	if _, err := pool.Exec(ctx, `INSERT INTO apartment_entry_code
		(apartment_id, position, code_type, custom_label, code_enc, valid_until, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $7)`, aptID, position, codeType, label, enc, until, ts); err != nil {
		t.Fatal(err)
	}
}

func TestStepEntryCodesApartmentEntryCodeTable(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	_, apt := testOwnerApartment(t, ctx, pool)
	insertEntryCode(t, ctx, pool, apt, 1, "building_entrance", "", "enc-expired", "2020-01-01")
	insertEntryCode(t, ctx, pool, apt, 2, "gate", "", "enc-future", "2030-01-01")
	insertEntryCode(t, ctx, pool, apt, 3, "garage", "", "enc-open", "")
	nDry, err := stepEntryCodes(ctx, testRunner(t, pool, true, nil))
	if err != nil || nDry != 1 {
		t.Fatalf("dry count %d err %v", nDry, err)
	}
	var left int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM apartment_entry_code WHERE apartment_id = $1`, apt).Scan(&left); err != nil || left != 3 {
		t.Fatalf("dry rows %d", left)
	}
	n, err := stepEntryCodes(ctx, testRunner(t, pool, false, nil))
	if err != nil || n != 1 {
		t.Fatalf("apply %d err %v", n, err)
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM apartment_entry_code WHERE apartment_id = $1`, apt).Scan(&left); err != nil || left != 2 {
		t.Fatalf("left %d", left)
	}
}

func TestStepEntryCodesArchivedApartmentDeletesRows(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	owner, apt := testOwnerApartment(t, ctx, pool)
	if _, err := pool.Exec(ctx, `UPDATE apartment SET archived_at = $1 WHERE id = $2`, "2020-01-01T00:00:00+00:00", apt); err != nil {
		t.Fatal(err)
	}
	insertEntryCode(t, ctx, pool, apt, 1, "gate", "", "enc-archived", "")
	owner64 := owner
	if n, err := stepEntryCodes(ctx, testRunner(t, pool, false, &owner64)); err != nil || n != 0 {
		t.Fatalf("owner %d err %v", n, err)
	}
	n, err := stepEntryCodes(ctx, testRunner(t, pool, false, nil))
	if err != nil || n != 1 {
		t.Fatalf("count %d err %v", n, err)
	}
	var left int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM apartment_entry_code WHERE apartment_id = $1`, apt).Scan(&left); err != nil || left != 0 {
		t.Fatalf("rows left %d", left)
	}
}

func TestApartmentEntryCodeConstraints(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	_, apt := testOwnerApartment(t, ctx, pool)
	ts := "2017-01-01T00:00:00+00:00"
	insertEntryCode(t, ctx, pool, apt, 1, "gate", "", "enc-a", "")
	if _, err := pool.Exec(ctx, `INSERT INTO apartment_entry_code
		(apartment_id, position, code_type, custom_label, code_enc, valid_until, created_at, updated_at)
		VALUES ($1, 1, 'gate', NULL, 'enc-b', NULL, $2, $2)`, apt, ts); err == nil {
		t.Fatal("duplicate position must fail")
	}
	if _, err := pool.Exec(ctx, `INSERT INTO apartment_entry_code
		(apartment_id, position, code_type, custom_label, code_enc, valid_until, created_at, updated_at)
		VALUES ($1, 2, 'other', NULL, 'enc-c', NULL, $2, $2)`, apt, ts); err == nil {
		t.Fatal("other without label must fail")
	}
	if _, err := pool.Exec(ctx, `INSERT INTO apartment_entry_code
		(apartment_id, position, code_type, custom_label, code_enc, valid_until, created_at, updated_at)
		VALUES ($1, 4, 'garage', NULL, 'enc-d', NULL, $2, $2)`, apt, ts); err == nil {
		t.Fatal("position 4 must fail")
	}
}
