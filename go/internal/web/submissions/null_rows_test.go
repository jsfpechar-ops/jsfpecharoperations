package submissions

import (
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

// seedNullRows inserts one owner, one apartment and two submission rows.
// Row 9101 has NULL mode, guest_ids and record_errors (older or hand-made rows).
// Row 9102 is a normal row.
func seedNullRows(t *testing.T, pool *pgxpool.Pool) (ownerID, aptID int64) {
	t.Helper()
	ctx := t.Context()
	stamp := "2026-11-01T10:00:00+00:00"
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at, email)
		VALUES ('null-rows', 'x', 'host', 1, 1, $1, 'null-rows@example.test') RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at) VALUES ($1,'Entity',$2) RETURNING id`,
		ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1,$2,'Null Flat','toknullrows','manual',24,1,$3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO submission (id, apartment_id, created_at, state) VALUES (9101, $1, $2, 'ok')`,
		aptID, stamp); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO submission (id, apartment_id, created_at, state, mode, guest_ids)
		VALUES (9102, $1, '2026-11-02T10:00:00+00:00', 'error', 'test', '[]')`, aptID); err != nil {
		t.Fatal(err)
	}
	return ownerID, aptID
}

func TestLoadListNullRows(t *testing.T) {
	pool := dbPool(t)
	owner, _ := seedNullRows(t, pool)
	page, err := LoadList(t.Context(), pool, owner)
	if err != nil {
		t.Fatalf("LoadList with NULL rows: %v", err)
	}
	if len(page.Rows) != 2 {
		t.Fatalf("rows = %d, want 2", len(page.Rows))
	}
	var nullRow *ListRow
	for i := range page.Rows {
		if page.Rows[i].ID == 9101 {
			nullRow = &page.Rows[i]
		}
	}
	if nullRow == nil {
		t.Fatal("NULL row 9101 missing from list")
	}
	if nullRow.Mode != "" {
		t.Errorf("Mode = %q, want empty", nullRow.Mode)
	}
	if nullRow.GuestIDs != "" {
		t.Errorf("GuestIDs = %q, want empty", nullRow.GuestIDs)
	}
	if nullRow.GuestCount != 0 {
		t.Errorf("GuestCount = %d, want 0", nullRow.GuestCount)
	}
}

func TestLoadDetailNullRow(t *testing.T) {
	pool := dbPool(t)
	owner, _ := seedNullRows(t, pool)
	page, ok, err := LoadDetail(t.Context(), pool, owner, 9101, "en")
	if err != nil {
		t.Fatalf("LoadDetail with NULL row: %v", err)
	}
	if !ok {
		t.Fatal("ok = false, want true")
	}
	if page.Submission.Mode != "" {
		t.Errorf("Mode = %q, want empty", page.Submission.Mode)
	}
	if len(page.Guests) != 0 {
		t.Errorf("Guests = %d, want 0", len(page.Guests))
	}
	if len(page.RecordErrors) != 0 {
		t.Errorf("RecordErrors = %d, want 0", len(page.RecordErrors))
	}
	if page.Submission.HeaderErrors != nil {
		t.Errorf("HeaderErrors = %v, want nil", *page.Submission.HeaderErrors)
	}
}
