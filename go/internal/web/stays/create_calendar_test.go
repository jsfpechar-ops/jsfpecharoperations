package stays

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

func createCalendarPost(t *testing.T, h http.Handler, at time.Time, nonce string, ownerID int64, fields map[string]string) (int, map[string]any) {
	t.Helper()
	if fields == nil {
		fields = map[string]string{}
	}
	fields["calendar"] = "1"
	fields["-accept"] = "application/json"
	rec := createCSRFPost(t, h, at, nonce, ownerID, fields)
	var body map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &body)
	return rec.Code, body
}

func seedCreateHost(t *testing.T, pool *pgxpool.Pool, now time.Time) (ownerID, aptID int64) {
	t.Helper()
	ctx := context.Background()
	stamp := isoStamp(now)
	name := t.Name()
	if len(name) > 48 {
		name = name[:48]
	}
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ($1, 'x', 'host', 1, 1, $2) RETURNING id`, name, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, ownerID, now)
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity', $2) RETURNING id`, ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1,$2,'Flat','tok-cal','manual',24,1,$3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	return ownerID, aptID
}

func TestReservationCreateCalendarJSONRejectsBadDates(t *testing.T) {
	pool := dbPool(t)
	now := time.Date(2026, 7, 1, 12, 0, 0, 0, time.UTC)
	ownerID, aptID := seedCreateHost(t, pool, now)
	mux := http.NewServeMux()
	Register(mux, pool, createGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	code, body := createCalendarPost(t, mux, now, "cal-bad-dates", ownerID, map[string]string{
		"apartment_id": fmt.Sprintf("%d", aptID),
		"date_from":    "2026-02-30",
		"date_to":      "2026-03-03",
	})
	if code != http.StatusUnprocessableEntity {
		t.Fatalf("code %d", code)
	}
	errs, _ := body["errors"].(map[string]any)
	if errs == nil || errs["date_to"] == nil {
		t.Fatalf("body %+v", body)
	}
}

func TestReservationCreateCalendarJSONRejectsBadGuestCount(t *testing.T) {
	pool := dbPool(t)
	now := time.Date(2026, 7, 1, 12, 0, 0, 0, time.UTC)
	ownerID, aptID := seedCreateHost(t, pool, now)
	mux := http.NewServeMux()
	Register(mux, pool, createGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	code, body := createCalendarPost(t, mux, now, "cal-bad-guests", ownerID, map[string]string{
		"apartment_id":    fmt.Sprintf("%d", aptID),
		"date_from":       "2026-08-01",
		"date_to":         "2026-08-03",
		"expected_guests": "0",
	})
	if code != http.StatusUnprocessableEntity {
		t.Fatalf("code %d", code)
	}
	errs, _ := body["errors"].(map[string]any)
	if errs == nil || errs["expected_guests"] == nil {
		t.Fatalf("body %+v", body)
	}
}

func TestReservationCreateCalendarJSONOverlapConflict(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 1, 12, 0, 0, 0, time.UTC)
	stamp := isoStamp(now)
	ownerID, aptID := seedCreateHost(t, pool, now)
	if _, err := pool.Exec(ctx, `INSERT INTO reservation (
		apartment_id, source, uid, date_from, date_to, status, created_at, updated_at)
		VALUES ($1,'manual','overlap-seed','2026-08-01','2026-08-03','active',$2,$2)`, aptID, stamp); err != nil {
		t.Fatal(err)
	}
	mux := http.NewServeMux()
	Register(mux, pool, createGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	var before int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM reservation WHERE apartment_id = $1`, aptID).Scan(&before); err != nil {
		t.Fatal(err)
	}
	code, body := createCalendarPost(t, mux, now, "cal-overlap", ownerID, map[string]string{
		"apartment_id": fmt.Sprintf("%d", aptID),
		"date_from":    "2026-08-02",
		"date_to":      "2026-08-04",
	})
	if code != http.StatusConflict {
		t.Fatalf("code %d body %+v", code, body)
	}
	if body["overlap"] != true {
		t.Fatalf("overlap flag %+v", body)
	}
	var after int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM reservation WHERE apartment_id = $1`, aptID).Scan(&after); err != nil {
		t.Fatal(err)
	}
	if after != before {
		t.Fatalf("rows %d -> %d", before, after)
	}
}

func TestReservationCreateCalendarJSONCreated(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 1, 12, 0, 0, 0, time.UTC)
	ownerID, aptID := seedCreateHost(t, pool, now)
	mux := http.NewServeMux()
	Register(mux, pool, createGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	rec := createCSRFPost(t, mux, now, "cal-create", ownerID, map[string]string{
		"calendar":        "1",
		"-accept":         "application/json",
		"apartment_id":    fmt.Sprintf("%d", aptID),
		"date_from":       "2026-09-01",
		"date_to":         "2026-09-03",
		"expected_guests": "2",
		"summary":         "Direct",
	})
	if rec.Code != http.StatusCreated {
		t.Fatalf("code %d %s", rec.Code, rec.Body.String())
	}
	if rec.Header().Get("Cache-Control") != "no-store" {
		t.Errorf("cache %q", rec.Header().Get("Cache-Control"))
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	idFloat, ok := body["id"].(float64)
	if !ok || idFloat < 1 {
		t.Fatalf("id %+v", body)
	}
	id := int64(idFloat)
	url, _ := body["url"].(string)
	if url == "" {
		t.Fatalf("url missing %+v", body)
	}
	var source, status string
	if err := pool.QueryRow(ctx, `SELECT source, status FROM reservation WHERE id = $1`, id).Scan(&source, &status); err != nil {
		t.Fatal(err)
	}
	if source != "manual" || status != "active" {
		t.Errorf("row %q %q", source, status)
	}
}
