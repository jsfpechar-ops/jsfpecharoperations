package guest

import (
	"context"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

func TestHasSamePersonGuestOnStay(t *testing.T) {
	pool := testPoolOptional(t)
	ctx := context.Background()

	var ownerID, aptID, resID, g1ID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, created_at) VALUES ('gdup2095@example.test', 'x', 'host', '2026-01-01T00:00:00Z') RETURNING id`).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, internal_name, uby_name, permalink_token, active, created_at) VALUES ($1, 'Guest Dup Apt', 'Guest Dup Apt', 'tokgdup2095', 1, '2026-01-01T00:00:00Z') RETURNING id`, ownerID).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, declared_guests, created_at, updated_at) VALUES ($1, 'uidgdup2095', '2026-06-01', '2026-06-04', 'active', 'manual', 2, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z') RETURNING id`, aptID).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO guest (reservation_id, surname, first_name, birth_date, nationality, submit_state, created_at, updated_at) VALUES ($1, 'Novak', 'Jan', '01021990', 'DEU', 'pending', '2026-06-01T10:00:00Z', '2026-06-01T10:00:00Z') RETURNING id`, resID).Scan(&g1ID); err != nil {
		t.Fatal(err)
	}

	d := saveDeps{
		pool:   pool,
		getenv: func(string) string { return "" },
		now:    func() time.Time { return time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC) },
	}

	// Submitting the exact same person as a new guest (excludeID=0) is blocked.
	dup, err := hasSamePersonGuestOnStay(ctx, d, resID, 0, validation.GuestRow{
		Surname: " novak ", FirstName: "JAN", BirthDate: "01021990", Nationality: "DEU",
	})
	if err != nil || !dup {
		t.Fatalf("expected duplicate detected, dup=%v err=%v", dup, err)
	}

	// Editing the same guest row (excludeID=g1ID) is allowed.
	dupSelf, err := hasSamePersonGuestOnStay(ctx, d, resID, g1ID, validation.GuestRow{
		Surname: "Novak", FirstName: "Jan", BirthDate: "01021990", Nationality: "DEU",
	})
	if err != nil || dupSelf {
		t.Fatalf("editing own guest row must not flag duplicate, dup=%v err=%v", dupSelf, err)
	}

	// Submitting a distinct second guest (child with different DOB) is allowed.
	dupChild, err := hasSamePersonGuestOnStay(ctx, d, resID, 0, validation.GuestRow{
		Surname: "Novak", FirstName: "Eva", BirthDate: "15052020", Nationality: "DEU", DocNumber: "INPASS",
	})
	if err != nil || dupChild {
		t.Fatalf("distinct child must not flag duplicate, dup=%v err=%v", dupChild, err)
	}
}
