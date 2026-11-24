package guest

import (
	"bytes"
	"context"
	"encoding/base64"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"
)

func TestPartyStartClaimMailOn(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	secret := strings.Repeat("k", 32)
	t.Setenv("UBYHOST_SECRET_KEY", secret)
	t.Setenv("UBYHOST_GUEST_PIN", "0")
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	t.Setenv("UBYHOST_PUBLIC_BASE_URL", "https://ubyhost.example")
	dataKey := base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{7}, 32))
	t.Setenv("UBYHOST_DATA_KEYS", dataKey)
	t.Setenv("UBYHOST_DATA_KEY_LEGACY", "0")
	getenv := func(k string) string {
		switch k {
		case "UBYHOST_SECRET_KEY":
			return secret
		case "UBYHOST_GUEST_PIN":
			return "0"
		case "UBYHOST_MAIL_BACKEND":
			return "console"
		case "UBYHOST_PUBLIC_BASE_URL":
			return "https://ubyhost.example"
		case "UBYHOST_DATA_KEYS":
			return base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{7}, 32))
		case "UBYHOST_DATA_KEY_LEGACY":
			return "0"
		}
		if v := os.Getenv(k); v != "" {
			return v
		}
		return ""
	}
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	wrap := func(_ string, h http.HandlerFunc) http.Handler { return h }

	mux := http.NewServeMux()
	RegisterStayClaim(mux, pool, getenv, now, wrap, nil)
	RegisterParty(mux, pool, getenv, now, wrap)

	aptID := time.Now().UnixNano()%8000000000 + 7000000
	userID := aptID
	resID := aptID + 1
	tok := fmt.Sprintf("claimstart%d", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("h%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
		VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4)`, aptID, userID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', $4, $5, $6, $6)`, resID, aptID, fmt.Sprintf("stay-%d", resID), "2026-06-10", "2026-06-12", stamp)

	getPath := fmt.Sprintf("/l/%s/%d?lang=en", tok, resID)
	getReq := httptest.NewRequest(http.MethodGet, getPath, nil)
	getRec := httptest.NewRecorder()
	mux.ServeHTTP(getRec, getReq)
	if getRec.Code != http.StatusOK {
		t.Fatalf("GET status %d", getRec.Code)
	}
	csrf := extractPageCSRF(getRec.Body.String())
	if csrf == "" {
		t.Fatal("missing page csrf")
	}
	csrfCookieVal := csrfCookie(getRec.Result().Cookies())
	if csrfCookieVal == "" {
		t.Fatal("missing ubyhost_csrf cookie")
	}

	postPath := fmt.Sprintf("/l/%s/%d/party?lang=en", tok, resID)
	body := url.Values{"_csrf": {csrf}, "party_size": {"2"}, "guest_email": {"guest@example.test"}}
	req := httptest.NewRequest(http.MethodPost, postPath, strings.NewReader(body.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfCookieVal})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d body %q", rec.Code, rec.Body.String())
	}
	loc := rec.Header().Get("Location")
	if !strings.Contains(loc, "claim_sent=1") {
		t.Fatalf("location %q", loc)
	}
	var state string
	if err := pool.QueryRow(ctx, `SELECT state FROM reservation_claim WHERE reservation_id = $1`, resID).Scan(&state); err != nil {
		t.Fatal(err)
	}
	if state != claimStateProvisional {
		t.Fatalf("state %q", state)
	}
}

func TestPartyMailEnabledConsoleBackend(t *testing.T) {
	getenv := func(k string) string {
		if k == "UBYHOST_MAIL_BACKEND" {
			return "console"
		}
		return ""
	}
	if !partyMailEnabled(getenv) {
		t.Fatal("console backend should enable mail-backed party")
	}
	getenvOff := func(k string) string {
		if k == "UBYHOST_MAIL_BACKEND" {
			return "disabled"
		}
		return ""
	}
	if partyMailEnabled(getenvOff) {
		t.Fatal("disabled backend should not enable mail-backed party")
	}
}
