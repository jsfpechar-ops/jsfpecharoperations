package guest

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

// stayClaimDeviceGate is Python's mail-on claim device check on the stay hub
// (guest.py stay_overview): DeviceHoldsClaim after claim.is_claimed, same cookie
// as formPagesRequireClaim (_require_claim_session).

func TestFormPagesRequireClaimMailOff(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "disabled")
	d := formPageDeps{getenv: func(k string) string { return os.Getenv(k) }, now: time.Now}
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rec := httptest.NewRecorder()
	apt := &Apartment{OwnerUserID: 1}
	res := formResRow{id: 9, status: "active"}
	if d.formPagesRequireClaim(rec, req, apt, res, "tok", "en") {
		t.Fatal("mail off must not gate")
	}
}

func TestFormPagesRequireClaimRedirectsWithoutDevice(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	secret := strings.Repeat("k", 32)
	getenv := guestTestGetenv(t, secret)
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	aptID := time.Now().UnixNano()%8000000000 + 7000000
	userID := aptID
	resID := aptID + 1
	tok := fmt.Sprintf("gatetok%d", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("g%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
		VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4)`, aptID, userID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', $4, $5, $6, $6)`, resID, aptID, fmt.Sprintf("stay-%d", resID), "2026-06-10", "2026-06-12", stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
		VALUES ($1, $2, '', 2, $3, $3) ON CONFLICT (reservation_id) DO UPDATE SET state = EXCLUDED.state, token_version = EXCLUDED.token_version`,
		resID, claimStateClaimed, stamp)

	d := formPageDeps{pool: pool, getenv: getenv, now: now}
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rec := httptest.NewRecorder()
	apt := &Apartment{ID: aptID, OwnerUserID: userID}
	res := formResRow{id: resID, status: "active"}
	if !d.formPagesRequireClaim(rec, req, apt, res, tok, "en") {
		t.Fatal("missing claim cookie must gate")
	}
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d want 303", rec.Code)
	}
	loc := rec.Header().Get("Location")
	if !strings.Contains(loc, fmt.Sprintf("/l/%s/%d", tok, resID)) {
		t.Fatalf("location %q", loc)
	}

	// Stale generation on the same stay.
	w := httptest.NewRecorder()
	rememberClaim(w, req, getenv, resID, 1)
	held := httptest.NewRequest(http.MethodGet, "/", nil)
	for _, c := range w.Result().Cookies() {
		if c.Name == claimCookieName {
			held.AddCookie(c)
		}
	}
	rec2 := httptest.NewRecorder()
	if !d.formPagesRequireClaim(rec2, held, apt, res, tok, "en") {
		t.Fatal("stale token_version must gate")
	}
}

func TestFormPagesNewRouteRedirectsWithoutClaim(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	secret := strings.Repeat("m", 32)
	getenv := guestTestGetenv(t, secret)
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	mux := http.NewServeMux()
	RegisterFormPages(mux, pool, getenv, now, func(_ string, h http.HandlerFunc) http.Handler { return h })

	aptID := time.Now().UnixNano()%8000000000 + 7100000
	userID := aptID
	resID := aptID + 1
	tok := fmt.Sprintf("newgate%d", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("n%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
		VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4)`, aptID, userID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at)
		VALUES ($1, $2, 1, $3)`, fmt.Sprintf("gate-%d-ab", aptID), aptID, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', $4, $5, $6, $6)`, resID, aptID, fmt.Sprintf("stay-%d", resID), "2026-06-10", "2026-06-12", stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
		VALUES ($1, $2, '', 1, $3, $3) ON CONFLICT (reservation_id) DO UPDATE SET state = EXCLUDED.state`,
		resID, claimStateClaimed, stamp)

	path := fmt.Sprintf("/l/%s/%d/new?lang=en", tok, resID)
	req := httptest.NewRequest(http.MethodGet, path, nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("GET %s status %d", path, rec.Code)
	}
	if loc := rec.Header().Get("Location"); !strings.Contains(loc, fmt.Sprintf("/l/%s/%d", tok, resID)) {
		t.Fatalf("redirect %q", loc)
	}

	// Device that holds the claim may open the form.
	w := httptest.NewRecorder()
	rememberClaim(w, req, getenv, resID, 1)
	held := httptest.NewRequest(http.MethodGet, path, nil)
	for _, c := range w.Result().Cookies() {
		if c.Name == claimCookieName {
			held.AddCookie(c)
		}
	}
	rec2 := httptest.NewRecorder()
	mux.ServeHTTP(rec2, held)
	if rec2.Code == http.StatusSeeOther && strings.Contains(rec2.Header().Get("Location"), fmt.Sprintf("/l/%s/%d", tok, resID)) && !strings.Contains(rec2.Header().Get("Location"), "/new") {
		t.Fatalf("held device should reach form, got redirect %q", rec2.Header().Get("Location"))
	}
}
