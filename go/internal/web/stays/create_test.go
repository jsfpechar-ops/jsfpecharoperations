package stays

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const createTestSecret = "stays-create-test-secret-32chars!"

func createGetenv(k string) string {
	switch k {
	case "UBYHOST_SECRET_KEY":
		return createTestSecret
	case "UBYHOST_TERMS_VERSION":
		return "t1"
	case "UBYHOST_PRIVACY_VERSION":
		return "p1"
	case "UBYHOST_DPA_VERSION":
		return "d1"
	default:
		return ""
	}
}

// seedLegalAcceptance matches properties_test: Login sends hosts without
// accepted terms to /account/accept (env versions t1, p1, d1).
func seedLegalAcceptance(t *testing.T, pool *pgxpool.Pool, userID int64, at time.Time) {
	t.Helper()
	ctx := context.Background()
	stamp := isoStamp(at)
	for j, doc := range []struct{ name, version string }{
		{"terms", "t1"}, {"privacy", "p1"}, {"dpa", "d1"},
	} {
		if _, err := pool.Exec(ctx, `INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method)
			VALUES ($1, $2, $3, $4, $5, 'clickwrap')`, userID*10+int64(j), userID, doc.name, doc.version, stamp); err != nil {
			t.Fatal(err)
		}
	}
}

func createCSRFPost(t *testing.T, h http.Handler, at time.Time, nonce string, ownerID int64, fields map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	form := url.Values{}
	for k, v := range fields {
		form.Set(k, v)
	}
	sum := sha256.Sum256([]byte(nonce))
	token, err := secure.NewTimedSerializer(createTestSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, at)
	if err != nil {
		t.Fatal(err)
	}
	form.Set("_csrf", token)
	req := httptest.NewRequest(http.MethodPost, "/reservations", strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: nonce})
	if ownerID != 0 {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(createTestSecret, map[string]any{
			"uid": ownerID, "sv": 1,
		}, at)})
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestRegisterRoutesPOST(t *testing.T) {
	mux := http.NewServeMux()
	Register(mux, nil, createGetenv, func() time.Time { return fixedToday() },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	req := httptest.NewRequest(http.MethodPost, "/reservations", nil)
	if h, p := mux.Handler(req); h == nil || p == "" {
		t.Fatalf("no POST handler pattern=%q", p)
	}
}

func TestReservationCreateMissingFieldsRedirects(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	now := fixedToday()
	stamp := isoStamp(now)
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('stays-create-miss', 'x', 'host', 1, 1, $1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, ownerID, now)
	mux := http.NewServeMux()
	Register(mux, pool, createGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	rec := createCSRFPost(t, mux, now, "nonce1", ownerID, map[string]string{})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("code %d, want 303", rec.Code)
	}
	loc := rec.Header().Get("Location")
	if !strings.HasPrefix(loc, "/reservations?") || !strings.Contains(loc, "err=") {
		t.Fatalf("location %q", loc)
	}
}

func TestReservationCreateInsertsRow(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 1, 12, 0, 0, 0, time.UTC)
	stamp := now.UTC().Format("2006-01-02T15:04:05") + "+00:00"
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('create-host', 'x', 'host', 1, 1, $1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, ownerID, now)
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity', $2) RETURNING id`, ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1,$2,'Flat','tok','manual',24,1,$3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	mux := http.NewServeMux()
	Register(mux, pool, createGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	rec := createCSRFPost(t, mux, now, "nonce2", 0, map[string]string{
		"apartment_id":    "1",
		"date_from":       "2026-08-01",
		"date_to":         "2026-08-03",
		"expected_guests": "2",
	})
	if rec.Code != http.StatusSeeOther || !strings.Contains(rec.Header().Get("Location"), "/login") {
		t.Fatalf("unsigned: code=%d loc=%q", rec.Code, rec.Header().Get("Location"))
	}
	rec = createCSRFPost(t, mux, now, "nonce3", ownerID, map[string]string{
		"apartment_id":    strconvFormat(aptID),
		"date_from":       "2026-08-01",
		"date_to":         "2026-08-03",
		"expected_guests": "2",
	})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("signed: code %d", rec.Code)
	}
	loc := rec.Header().Get("Location")
	if !strings.HasPrefix(loc, "/reservations/") || !strings.Contains(loc, "msg=") {
		t.Fatalf("location %q", loc)
	}
	if strings.Contains(loc, "flash.reservations.created") {
		t.Fatalf("flash key leaked in redirect: %q", loc)
	}
	if !strings.Contains(loc, "Stay+created") && !strings.Contains(loc, "Stay%20created") {
		t.Fatalf("expected translated create flash in %q", loc)
	}
	var count int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM reservation WHERE apartment_id = $1 AND date_from = '2026-08-01'`, aptID).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatalf("reservations=%d", count)
	}
}

func strconvFormat(id int64) string {
	return fmt.Sprintf("%d", id)
}

func TestReservationCreateStartsClaimOnGuestEmail(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	t.Setenv("PUBLIC_BASE_URL", "https://ubyhost.example")
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 2, 12, 0, 0, 0, time.UTC)
	stamp := isoStamp(now)
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('create-claim-host', 'x', 'host', 1, 1, $1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, ownerID, now)
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity', $2) RETURNING id`, ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1,$2,'Claim flat','claimcreatetok','manual',24,1,$3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	getenv := func(k string) string {
		switch k {
		case "PUBLIC_BASE_URL":
			return "https://ubyhost.example"
		default:
			return createGetenv(k)
		}
	}
	mux := http.NewServeMux()
	Register(mux, pool, getenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	rec := createCSRFPost(t, mux, now, "nonce-create-claim", ownerID, map[string]string{
		"apartment_id":    strconvFormat(aptID),
		"date_from":       "2026-08-01",
		"date_to":         "2026-08-03",
		"expected_guests": "2",
		"guest_email":     " newguest@example.test ",
	})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("create: code %d", rec.Code)
	}
	loc := rec.Header().Get("Location")
	var resID int64
	if _, err := fmt.Sscanf(loc, "/reservations/%d", &resID); err != nil {
		t.Fatalf("parse reservation id from %q: %v", loc, err)
	}
	var auditN int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM audit WHERE action = 'guest_link_sent_on_create' AND detail = $1`,
		fmt.Sprintf("reservation=%d", resID)).Scan(&auditN); err != nil || auditN != 1 {
		t.Fatalf("audit guest_link_sent_on_create count=%d err=%v", auditN, err)
	}
	var claimState string
	if err := pool.QueryRow(ctx, `SELECT state FROM reservation_claim WHERE reservation_id = $1`, resID).Scan(&claimState); err != nil {
		t.Fatal(err)
	}
	if claimState != claimStateProvisional {
		t.Fatalf("claim state %q, want provisional", claimState)
	}
	var outboxN int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = $1`,
		fmt.Sprintf("claim:%d:v1", resID)).Scan(&outboxN); err != nil || outboxN != 1 {
		t.Fatalf("claim outbox count=%d err=%v", outboxN, err)
	}
}

func TestReservationCreateSkipsClaimWithoutGuestEmail(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	pool := dbPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 3, 12, 0, 0, 0, time.UTC)
	stamp := isoStamp(now)
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('create-no-email', 'x', 'host', 1, 1, $1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, ownerID, now)
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity', $2) RETURNING id`, ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, submit_after_hours, active, created_at)
		VALUES ($1,$2,'No mail flat','nomailtok','manual',24,1,$3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	mux := http.NewServeMux()
	Register(mux, pool, createGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	rec := createCSRFPost(t, mux, now, "nonce-create-no-mail", ownerID, map[string]string{
		"apartment_id":    strconvFormat(aptID),
		"date_from":       "2026-09-01",
		"date_to":         "2026-09-03",
		"expected_guests": "2",
	})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("create: code %d", rec.Code)
	}
	var resID int64
	if _, err := fmt.Sscanf(rec.Header().Get("Location"), "/reservations/%d", &resID); err != nil {
		t.Fatalf("location %q", rec.Header().Get("Location"))
	}
	var auditN int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM audit WHERE action = 'guest_link_sent_on_create' AND detail = $1`,
		fmt.Sprintf("reservation=%d", resID)).Scan(&auditN); err != nil || auditN != 0 {
		t.Fatalf("unexpected audit count=%d err=%v", auditN, err)
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM reservation_claim WHERE reservation_id = $1`, resID).Scan(&auditN); err != nil {
		t.Fatal(err)
	}
	if auditN != 0 {
		t.Fatalf("claim row count=%d without guest email", auditN)
	}
}
