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

func TestDeviceHoldsClaimCookieRoundTrip(t *testing.T) {
	env := testGuestEnv
	req := httptest.NewRequest(http.MethodGet, "/l/tok/9", nil)
	if DeviceHoldsClaim(req, env, 9, 1) {
		t.Fatal("empty cookie must not hold the claim")
	}
	w := httptest.NewRecorder()
	rememberClaim(w, req, env, 9, 1)
	res := w.Result()
	defer res.Body.Close()
	var cookie *http.Cookie
	for _, c := range res.Cookies() {
		if c.Name == claimCookieName {
			cookie = c
		}
	}
	if cookie == nil {
		t.Fatal("ubyhost_claim cookie not set")
	}
	held := httptest.NewRequest(http.MethodGet, "/l/tok/9", nil)
	held.AddCookie(cookie)
	if !DeviceHoldsClaim(held, env, 9, 1) {
		t.Fatal("device must hold generation 1")
	}
	if DeviceHoldsClaim(held, env, 9, 2) {
		t.Fatal("stale generation must not hold")
	}
	if DeviceHoldsClaim(held, env, 8, 1) {
		t.Fatal("other stay must not hold")
	}
}

func TestRememberClaimKeepsPriorStays(t *testing.T) {
	env := testGuestEnv
	first := httptest.NewRecorder()
	rememberClaim(first, httptest.NewRequest(http.MethodGet, "/", nil), env, 11, 3)
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	for _, c := range first.Result().Cookies() {
		if c.Name == claimCookieName {
			req.AddCookie(c)
		}
	}
	second := httptest.NewRecorder()
	rememberClaim(second, req, env, 12, 1)
	out := httptest.NewRequest(http.MethodGet, "/", nil)
	for _, c := range second.Result().Cookies() {
		if c.Name == claimCookieName {
			out.AddCookie(c)
		}
	}
	if !DeviceHoldsClaim(out, env, 11, 3) || !DeviceHoldsClaim(out, env, 12, 1) {
		t.Fatal("cookie must keep both stays")
	}
}

func TestConfirmClaimAppliesDeclaredGuests(t *testing.T) {
	pool := testPool(t)
	if pool == nil {
		t.Skip("UBYHOST_TEST_DATABASE_URL")
	}
	ctx := context.Background()
	var schemaOK int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'apartment'`).Scan(&schemaOK); err != nil || schemaOK == 0 {
		t.Skip("needs migrated Postgres schema")
	}
	secret, err := newClaimSecret()
	if err != nil {
		t.Fatal(err)
	}
	stamp := isoNow(time.Now().UTC())
	hash := claimTokenHash(secret)
	aptID := int64(172198)
	resID := int64(172199)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, permalink_token, active, created_at)
		VALUES ($1, 1, 'Flat', 'claimtok-declared', 1, $2) ON CONFLICT (id) DO NOTHING`, aptID, stamp)
	mustExec(t, pool, `INSERT INTO reservation (id, apartment_id, status, source, date_from, date_to, created_at)
		VALUES ($1, $2, 'active', 'ical', '2026-06-01', '2026-06-05', $3) ON CONFLICT (id) DO NOTHING`, resID, aptID, stamp)
	mustExec(t, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, declared_guests, created_at, updated_at)
		VALUES ($1, $2, $3, 1, 3, $4, $4) ON CONFLICT (reservation_id) DO UPDATE SET
			state = EXCLUDED.state, token_hash = EXCLUDED.token_hash, token_version = 1, declared_guests = 3`,
		resID, claimStateProvisional, hash, stamp)
	ok, err := confirmClaim(ctx, pool, resID, secret, &scApt{id: aptID, token: "claimtok-declared"}, &scStay{id: resID, status: "active"}, time.Now().UTC())
	if err != nil {
		t.Fatal(err)
	}
	if !ok {
		t.Fatal("confirm should succeed")
	}
	var declared *int64
	if err := pool.QueryRow(ctx, `SELECT declared_guests FROM reservation WHERE id = $1`, resID).Scan(&declared); err != nil {
		t.Fatal(err)
	}
	if declared == nil || *declared != 3 {
		t.Fatalf("declared_guests=%v want 3", declared)
	}
}

func TestStayOverviewMailOnHonorsClaimCookie(t *testing.T) {
	pool := testPool(t)
	if pool == nil {
		t.Skip("UBYHOST_TEST_DATABASE_URL")
	}
	ctx := context.Background()
	var schemaOK int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'apartment'`).Scan(&schemaOK); err != nil || schemaOK == 0 {
		t.Skip("needs migrated Postgres schema")
	}
	secret := strings.Repeat("c", 32)
	t.Setenv("UBYHOST_SECRET_KEY", secret)
	t.Setenv("UBYHOST_GUEST_PIN", "0")
	t.Setenv("UBYHOST_MAIL_BACKEND", "ses")
	getenv := func(k string) string {
		if v := os.Getenv(k); v != "" {
			return v
		}
		return ""
	}
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	stamp := isoNow(now())
	aptID := int64(172210)
	resID := int64(172211)
	tok := "claimtok-cookie"
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, permalink_token, active, created_at)
		VALUES ($1, 1, 'Flat', $2, 1, $3) ON CONFLICT (id) DO NOTHING`, aptID, tok, stamp)
	mustExec(t, pool, `INSERT INTO reservation (id, apartment_id, status, source, date_from, date_to, created_at)
		VALUES ($1, $2, 'active', 'ical', '2026-06-10', '2026-06-12', $3) ON CONFLICT (id) DO NOTHING`, resID, aptID, stamp)
	mustExec(t, pool, `INSERT INTO reservation_claim (reservation_id, state, token_version, created_at, updated_at)
		VALUES ($1, $2, 1, $3, $3) ON CONFLICT (reservation_id) DO UPDATE SET state = EXCLUDED.state, token_version = 1`,
		resID, claimStateClaimed, stamp)

	d := stayClaimDeps{pool: pool, getenv: getenv, now: now}
	bare := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d?lang=en", tok, resID), nil)
	bare.SetPathValue("token", tok)
	bare.SetPathValue("reservation_id", fmt.Sprintf("%d", resID))
	assigned := httptest.NewRecorder()
	d.stayOverview(assigned, bare)
	if assigned.Code != http.StatusOK || !strings.Contains(assigned.Body.String(), "guest-assigned") {
		t.Fatalf("without cookie: status %d body %q", assigned.Code, assigned.Body.String())
	}

	set := httptest.NewRecorder()
	rememberClaim(set, bare, getenv, resID, 1)
	held := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d?lang=en", tok, resID), nil)
	held.SetPathValue("token", tok)
	held.SetPathValue("reservation_id", fmt.Sprintf("%d", resID))
	for _, c := range set.Result().Cookies() {
		if c.Name == claimCookieName {
			held.AddCookie(c)
		}
	}
	okRec := httptest.NewRecorder()
	d.stayOverview(okRec, held)
	if okRec.Code != http.StatusSeeOther {
		t.Fatalf("with cookie: status %d body %q", okRec.Code, okRec.Body.String())
	}
	if loc := okRec.Header().Get("Location"); !strings.Contains(loc, "/new") {
		t.Fatalf("with cookie location %q", loc)
	}
}
