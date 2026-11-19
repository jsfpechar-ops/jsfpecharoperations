package doorcodes

import (
	"context"
	"reflect"
	"testing"
	"time"
)

func TestViewForStay(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	s := &Service{Pool: pool, Settings: Settings{Enabled: true, Live: true}}

	got, err := s.ViewForStay(ctx, 999999, 999999)
	if err != nil {
		t.Fatal(err)
	}
	if got != nil {
		t.Fatalf("missing rows: got %v", got)
	}

	now := time.Date(2026, 11, 19, 12, 0, 0, 0, time.UTC)
	stamp := now.Format("2006-01-02T15:04:05")
	var aptID int64
	if err := pool.QueryRow(ctx,
		"INSERT INTO apartment (internal_name, owner_user_id, lock_provider, lock_id, checkin_hour, checkout_hour, created_at) "+
			"VALUES ('Test flat', 7, 'ttlock', '555', 14, 10, $1) RETURNING id", stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	var resID int64
	if err := pool.QueryRow(ctx,
		"INSERT INTO reservation (apartment_id, uid, date_from, date_to, registration_completed_at, status, source, created_at, updated_at) "+
			"VALUES ($1, $2, '2026-11-15', '2026-11-18', $3, 'active', 'manual', $3, $3) RETURNING id",
		aptID, "uid-view-stay", stamp).Scan(&resID); err != nil {
		t.Fatal(err)
	}

	r, err := s.loadReservation(ctx, resID)
	if err != nil || r == nil {
		t.Fatalf("loadReservation: %v %v", r, err)
	}
	a, err := s.loadApartment(ctx, aptID)
	if err != nil || a == nil {
		t.Fatalf("loadApartment: %v %v", a, err)
	}
	want, werr := s.View(ctx, *r, *a)
	got, gerr := s.ViewForStay(ctx, resID, aptID)
	if werr != nil || gerr != nil {
		t.Fatalf("errors w=%v g=%v", werr, gerr)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("ViewForStay != View:\nwant %+v\ngot  %+v", want, got)
	}
}
