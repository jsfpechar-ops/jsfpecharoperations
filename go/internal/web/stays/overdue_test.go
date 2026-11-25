package stays

import (
	"context"
	"net/url"
	"os"
	"testing"
	"time"
)

// Regression for Go parity / WP33 (2018): a stay whose guests have left but a
// guest is still unfiled must stay in overdueUnfinishedIDs so the default Stays
// list keeps it visible.
func TestOverdueUnfinishedIDsIncludesDepartedUnfiled(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	stamp := now

	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('overdue-host', 'x', 'host', 1, 1, $1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity', $2) RETURNING id`, ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1, $2, 'Flat', 'tok', 'manual', 24, 1, $3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}

	var overdueID int64
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, declared_guests, created_at, updated_at)
		VALUES ($1, 'old-unfiled', '2026-05-10', '2026-05-12', 'active', 'manual', 1, $2, $2) RETURNING id`,
		aptID, stamp).Scan(&overdueID); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO guest (reservation_id, surname, nationality, stay_from, submit_state, is_lead, entered_by, created_at, updated_at)
		VALUES ($1, 'Unfiled', 'DEU', '2026-05-10', 'pending', 1, 'guest', $2, $2)`, overdueID, stamp); err != nil {
		t.Fatal(err)
	}

	var futureID int64
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, declared_guests, created_at, updated_at)
		VALUES ($1, 'future', '2026-06-20', '2026-06-22', 'active', 'manual', 1, $2, $2) RETURNING id`,
		aptID, stamp).Scan(&futureID); err != nil {
		t.Fatal(err)
	}

	getenv := func(k string) string { return os.Getenv(k) }
	ids, err := overdueUnfinishedIDs(ctx, pool, getenv, ownerID, now)
	if err != nil {
		t.Fatal(err)
	}
	found := false
	for _, id := range ids {
		if id == overdueID {
			found = true
		}
		if id == futureID {
			t.Fatalf("future stay %d must not be overdue", futureID)
		}
	}
	if !found {
		t.Fatalf("departed unfiled stay %d missing from overdue IDs %v", overdueID, ids)
	}
}

func TestUpcomingListKeepsDepartedOverdueUnfiled(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	stamp := now

	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('list-overdue-host', 'x', 'host', 1, 1, $1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity', $2) RETURNING id`, ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1, $2, 'Flat', 'tok', 'manual', 24, 1, $3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	var resID int64
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, declared_guests, created_at, updated_at)
		VALUES ($1, 'scope-overdue', '2026-05-10', '2026-05-12', 'active', 'manual', 1, $2, $2) RETURNING id`,
		aptID, stamp).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO guest (reservation_id, surname, nationality, stay_from, submit_state, is_lead, entered_by, created_at, updated_at)
		VALUES ($1, 'SCOPEOVERDUE', 'DEU', '2026-05-10', 'pending', 1, 'guest', $2, $2)`, resID, stamp); err != nil {
		t.Fatal(err)
	}

	getenv := func(k string) string { return os.Getenv(k) }
	p := ParseParams(url.Values{"range": {"upcoming"}}, now)
	view, err := List(ctx, pool, getenv, ownerID, p, now)
	if err != nil {
		t.Fatal(err)
	}
	var seen bool
	for _, row := range view.Rows {
		if row.Reservation.ID == resID {
			seen = true
			break
		}
	}
	if !seen {
		t.Fatalf("upcoming list must include departed overdue stay %d (rows=%d)", resID, len(view.Rows))
	}
}

func TestOverdueUnfinishedIDsPragueDateNearMidnight(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	// 23:30 UTC on Nov 24 is 00:30 CET on Nov 25 in Prague.
	at := time.Date(2026, 11, 24, 23, 30, 0, 0, time.UTC)

	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('overdue-prague-host', 'x', 'host', 1, 1, $1) RETURNING id`, at).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity', $2) RETURNING id`, ownerID, at).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1, $2, 'Flat', 'tok', 'manual', 24, 1, $3) RETURNING id`, ownerID, entityID, at).Scan(&aptID); err != nil {
		t.Fatal(err)
	}

	insertUnfiled := func(uid, from, to string) int64 {
		t.Helper()
		var id int64
		if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, declared_guests, created_at, updated_at)
			VALUES ($1, $2, $3, $4, 'active', 'manual', 1, $5, $5) RETURNING id`,
			aptID, uid, from, to, at).Scan(&id); err != nil {
			t.Fatal(err)
		}
		if _, err := pool.Exec(ctx, `INSERT INTO guest (reservation_id, surname, nationality, stay_from, submit_state, is_lead, entered_by, created_at, updated_at)
			VALUES ($1, 'Unfiled', 'DEU', $2, 'pending', 1, 'guest', $3, $3)`, id, from, at); err != nil {
			t.Fatal(err)
		}
		return id
	}

	// 46 days before Prague Nov 25 (45 days before UTC Nov 24) -> excluded.
	excludedID := insertUnfiled("prague-46d", "2026-10-10", "2026-10-12")
	// 45 days before Prague Nov 25 -> included.
	includedID := insertUnfiled("prague-45d", "2026-10-11", "2026-10-13")

	getenv := func(k string) string { return os.Getenv(k) }
	ids, err := overdueUnfinishedIDs(ctx, pool, getenv, ownerID, at)
	if err != nil {
		t.Fatal(err)
	}
	var sawIncluded bool
	for _, id := range ids {
		if id == excludedID {
			t.Fatalf("46-day-old stay %d (2026-10-10) must be excluded on Prague 2026-11-25; ids=%v", excludedID, ids)
		}
		if id == includedID {
			sawIncluded = true
		}
	}
	if !sawIncluded {
		t.Fatalf("45-day-old stay %d (2026-10-11) missing on Prague 2026-11-25; ids=%v", includedID, ids)
	}

	// Verify ParseParams(pragueToday(at)) and List ORDER BY todayISO use Prague 2026-11-25.
	var pastInPragueID, todayInPragueID int64
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
		VALUES ($1, 'prague-yesterday', '2026-11-24', '2026-11-24', 'active', 'manual', $2, $2) RETURNING id`,
		aptID, at).Scan(&pastInPragueID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, created_at, updated_at)
		VALUES ($1, 'prague-today', '2026-11-25', '2026-11-26', 'active', 'manual', $2, $2) RETURNING id`,
		aptID, at).Scan(&todayInPragueID); err != nil {
		t.Fatal(err)
	}

	pUpcoming := ParseParams(url.Values{"range": {"upcoming"}}, pragueToday(at))
	if pUpcoming.DateFrom != "2026-11-25" {
		t.Fatalf("upcoming DateFrom = %q, want 2026-11-25", pUpcoming.DateFrom)
	}
	pAll := ParseParams(url.Values{"range": {"all"}}, pragueToday(at))
	vAll, err := List(ctx, pool, getenv, ownerID, pAll, at)
	if err != nil {
		t.Fatal(err)
	}
	if len(vAll.Rows) < 2 || vAll.Rows[0].Reservation.ID != todayInPragueID || vAll.Rows[1].Reservation.ID != pastInPragueID {
		t.Fatalf("range=all order mismatch: got first two IDs %v, want [%d, %d]", vAll.Rows, todayInPragueID, pastInPragueID)
	}
}
