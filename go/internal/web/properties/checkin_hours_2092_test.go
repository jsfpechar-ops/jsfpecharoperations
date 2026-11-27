package properties

import (
	"context"
	"net/http"
	"strings"
	"testing"
)

func TestApartmentCreateRequiresTimesAndDefaultsScheduled24h(t *testing.T) {
	g := loadApartmentCreateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, g)
	mux := http.NewServeMux()
	RegisterApartmentCreate(mux, noWrap, pool, apartmentCreateGetenv, testClock)

	// 1. Missing checkin_hour / checkout_hour must be refused with HTTP 400.
	missingTimes := map[string]string{
		"internal_name":   "No Times Flat",
		"legal_entity_id": "21",
		"addr_street":     "Dlouha", "addr_house_no": "5", "addr_zip": "11000", "addr_obec": "Praha",
	}
	rec := apartmentCreatePost(t, mux, g.CSRFNonce, 2, 0, "en", true, missingTimes)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("missing times status = %d, want 400", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `id="times-error"`) {
		t.Fatalf("missing times body did not render times-error")
	}

	// 2. Valid checkin_hour=16, checkout_hour=11 persists them and defaults to scheduled + 24 h.
	valid := map[string]string{
		"internal_name":   "Scheduled Default Flat",
		"legal_entity_id": "21",
		"addr_street":     "Dlouha", "addr_house_no": "5", "addr_zip": "11000", "addr_obec": "Praha",
		"checkin_hour": "16", "checkout_hour": "11",
	}
	before := apartmentCreateMaxID(t, pool)
	rec = apartmentCreatePost(t, mux, g.CSRFNonce, 2, 0, "en", true, valid)
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("valid create status = %d, want 303", rec.Code)
	}
	id := apartmentCreateMaxID(t, pool)
	if id == before {
		t.Fatal("apartment row was not inserted")
	}
	var mode string
	var hours, cin, cout int64
	if err := pool.QueryRow(context.Background(),
		`SELECT automation_mode, submit_after_hours, checkin_hour, checkout_hour FROM apartment WHERE id = $1`, id,
	).Scan(&mode, &hours, &cin, &cout); err != nil {
		t.Fatal(err)
	}
	if mode != "scheduled" || hours != 24 || cin != 16 || cout != 11 {
		t.Fatalf("created row = mode:%q hours:%d cin:%d cout:%d, want scheduled 24 16 11", mode, hours, cin, cout)
	}
}

func TestApartmentUpdateRefusesBlankTimesAndHoursAbove24(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, pool, apartmentUpdateGetenv, testClock)

	// 1. Refuses clearing checkin_hour to blank.
	rec := apartmentFormPost(t, mux, "/apartments/201", g.CSRFNonce, 2, 0, "en", true, map[string]string{
		"internal_name": "Loft", "legal_entity_id": "21",
		"checkin_hour": "", "checkout_hour": "10",
	})
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("blank checkin_hour status = %d, want 400", rec.Code)
	}

	// 2. Refuses submit_after_hours = 25 in scheduled mode.
	rec = apartmentFormPost(t, mux, "/apartments/201", g.CSRFNonce, 2, 0, "en", true, map[string]string{
		"internal_name": "Loft", "legal_entity_id": "21",
		"checkin_hour": "15", "checkout_hour": "10",
		"automation_mode": "scheduled", "submit_after_hours": "25",
	})
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("submit_after_hours=25 status = %d, want 400", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "from 1 to 24") {
		t.Fatalf("expected 1..24 timing error message in body")
	}

	// 3. Accepts submit_after_hours = 24 in scheduled mode.
	rec = apartmentFormPost(t, mux, "/apartments/201", g.CSRFNonce, 2, 0, "en", true, map[string]string{
		"internal_name": "Loft", "legal_entity_id": "21",
		"checkin_hour": "15", "checkout_hour": "10",
		"automation_mode": "scheduled", "submit_after_hours": "24",
	})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("submit_after_hours=24 status = %d, want 303", rec.Code)
	}
}
