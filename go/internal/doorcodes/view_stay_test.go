package doorcodes

import (
	"context"
	"fmt"
	"reflect"
	"testing"
	"time"
)

func TestViewForStay(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Date(2026, 11, 19, 12, 0, 0, 0, time.UTC)
	s := &Service{Pool: pool, Settings: Settings{Enabled: true, Live: true}, Clock: &fakeClock{t: now}}

	got, err := s.ViewForStay(ctx, 999999, 999999)
	if err != nil {
		t.Fatal(err)
	}
	if got != nil {
		t.Fatalf("missing rows: got %v", got)
	}

	stamp := now.Format("2006-01-02T15:04:05")
	var ownerID int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO user_account (username, password_hash, role, active, session_version, created_at) VALUES ($1,'x','host',1,1,$2) RETURNING id`,
		"view-stay-host-"+t.Name(), now).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	token := fmt.Sprintf("tok-view-stay-%d", time.Now().UnixNano())
	var aptID int64
	if err := pool.QueryRow(ctx,
		"INSERT INTO apartment (internal_name, owner_user_id, lock_provider, lock_id, checkin_hour, checkout_hour, permalink_token, created_at) "+
			"VALUES ('Test flat', $1, 'ttlock', '555', 14, 10, $2, $3) RETURNING id", ownerID, token, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	var resID int64
	uid := fmt.Sprintf("uid-view-stay-%d", time.Now().UnixNano())
	if err := pool.QueryRow(ctx,
		"INSERT INTO reservation (apartment_id, uid, date_from, date_to, registration_completed_at, status, source, created_at, updated_at) "+
			"VALUES ($1, $2, '2026-11-15', '2026-11-18', $3, 'active', 'manual', $3, $3) RETURNING id",
		aptID, uid, stamp).Scan(&resID); err != nil {
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

func TestIssuedViewAcrossDST(t *testing.T) {
	s := &Service{}
	cin := int64(15)
	cout := int64(11)
	apt := Apartment{ID: 1, CheckinHour: &cin, CheckoutHour: &cout}

	cases := []struct {
		name           string
		dateFrom       string
		dateTo         string
		validFrom      string
		validTo        string
		wantWorksFrom  string
		wantWorksUntil string
		wantFirstUseBy string
	}{
		{
			name:           "spring forward (23h day: 14:00 CET + 24h = 15:00 CEST)",
			dateFrom:       "2026-03-28",
			dateTo:         "2026-03-30",
			validFrom:      "2026-03-28T13:00:00+00:00",
			validTo:        "2026-03-30T10:00:00+00:00",
			wantWorksFrom:  "28.03.2026 14:00",
			wantWorksUntil: "30.03.2026 12:00",
			wantFirstUseBy: "29.03.2026 15:00",
		},
		{
			name:           "fall back (25h day: 14:00 CEST + 24h = 13:00 CET)",
			dateFrom:       "2026-10-24",
			dateTo:         "2026-10-26",
			validFrom:      "2026-10-24T12:00:00+00:00",
			validTo:        "2026-10-26T11:00:00+00:00",
			wantWorksFrom:  "24.10.2026 14:00",
			wantWorksUntil: "26.10.2026 12:00",
			wantFirstUseBy: "25.10.2026 13:00",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			vf, vt := tc.validFrom, tc.validTo
			shown, err := s.issuedView(
				Reservation{ID: 1, DateFrom: tc.dateFrom, DateTo: tc.dateTo},
				apt,
				&doorCode{ValidFrom: &vf, ValidTo: &vt},
				"123456",
			)
			if err != nil {
				t.Fatalf("issuedView: %v", err)
			}
			if shown.WorksFrom != tc.wantWorksFrom || shown.WorksUntil != tc.wantWorksUntil || shown.FirstUseBy != tc.wantFirstUseBy {
				t.Fatalf("got %+v, want from=%q until=%q firstUse=%q", shown, tc.wantWorksFrom, tc.wantWorksUntil, tc.wantFirstUseBy)
			}
		})
	}
}
