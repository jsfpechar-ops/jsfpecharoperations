package guest

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

func TestPickStayPinPageHTTP(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	secret := strings.Repeat("x", 32)
	t.Setenv("UBYHOST_SECRET_KEY", secret)
	t.Setenv("UBYHOST_GUEST_PIN", "1")
	getenv := func(k string) string {
		if v := os.Getenv(k); v != "" {
			return v
		}
		return ""
	}
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	mux := http.NewServeMux()
	RegisterShell(mux, pool, getenv, now, func(_ string, h http.HandlerFunc) http.Handler { return h })

	ctx := t.Context()
	stamp := "2026-01-01T00:00:00Z"
	aptID := time.Now().UnixNano()%9000000000 + 2000000
	userID := aptID
	tok := fmt.Sprintf("perm%dtok", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("p%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, permalink_pin, created_at)
		VALUES ($1, $2, 'Flat', 'Prague', 1, $3, '123456', $4)`, aptID, userID, tok, stamp)

	req := httptest.NewRequest(http.MethodGet, "/l/"+tok+"?lang=en", nil)
	rec := httptest.NewRecorder()
	start := time.Now()
	mux.ServeHTTP(rec, req)
	if elapsed := time.Since(start); elapsed > 2*time.Second {
		t.Fatalf("pick_stay took %v, want under 2s", elapsed)
	}
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d body %q", rec.Code, rec.Body.String()[:min(200, rec.Body.Len())])
	}
	body := rec.Body.String()
	if !strings.Contains(body, "pin") && !strings.Contains(body, "PIN") {
		t.Fatalf("expected PIN form, got snippet %q", body[:min(300, len(body))])
	}
}

func TestPinRedirectHonoursSession(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	secret := strings.Repeat("y", 32)
	t.Setenv("UBYHOST_SECRET_KEY", secret)
	t.Setenv("UBYHOST_GUEST_PIN", "1")
	getenv := func(k string) string {
		if v := os.Getenv(k); v != "" {
			return v
		}
		return ""
	}
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	ctx := t.Context()
	stamp := "2026-01-01T00:00:00Z"
	aptID := time.Now().UnixNano()%9000000000 + 3000000
	userID := aptID
	tok := fmt.Sprintf("pinredir%d", aptID)
	resID := aptID + 1
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("r%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, permalink_pin, created_at)
		VALUES ($1, $2, 'Flat', 'Prague', 1, $3, '123456', $4)`, aptID, userID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', $4, $5, $6, $6)`, resID, aptID, fmt.Sprintf("stay-%d", resID), "2026-06-10", "2026-06-12", stamp)

	d := stayClaimDeps{pool: pool, getenv: getenv, now: now}
	pinRec := httptest.NewRecorder()
	if err := attachPinSession(pinRec, secret, tok, "123456", getenv, now()); err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d?lang=en", tok, resID), nil)
	for _, c := range pinRec.Result().Cookies() {
		req.AddCookie(c)
	}
	stayRec := httptest.NewRecorder()
	if redir := d.pinRedirect(stayRec, req, tok, "en", resID); redir {
		t.Fatalf("expected no hub redirect with pin session, got Location %q", stayRec.Header().Get("Location"))
	}
}
