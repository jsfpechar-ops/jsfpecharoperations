package booking

import (
	"context"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

func TestParseRailsFormRequiresRail(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	seedRailApartment(t, pool, 50)
	_, err := ParseRailsForm(ctx, pool, 50, nil, "", "", "iban")
	if err == nil || err.Error() != "pay_none" {
		t.Fatalf("got %v, want pay_none", err)
	}
}

func TestParseRailsFormRevolutBad(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	seedRailApartment(t, pool, 51)
	_, err := ParseRailsForm(ctx, pool, 51, []string{"revolut"}, "not-a-url", "", "")
	if err == nil || err.Error() != "pay_revolut" {
		t.Fatalf("got %v, want pay_revolut", err)
	}
}

func seedRailApartment(t *testing.T, pool *pgxpool.Pool, id int64) {
	t.Helper()
	_, err := pool.Exec(context.Background(), `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES (1, 'host1', 'x', 'host', 1, '2026-01-01T00:00:00+00:00') ON CONFLICT (id) DO NOTHING`)
	if err != nil {
		t.Fatal(err)
	}
	_, err = pool.Exec(context.Background(), `INSERT INTO apartment (id, owner_user_id, internal_name, created_at, stay_fee_guest_rails, active)
		VALUES ($1, 1, 'Test', '2026-01-01T00:00:00+00:00', 'iban', 1) ON CONFLICT (id) DO NOTHING`, id)
	if err != nil {
		t.Fatal(err)
	}
}