package guest

import (
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"
)

func extractPageCSRF(html string) string {
	const open = `name="_csrf" value="`
	i := strings.Index(html, open)
	if i < 0 {
		return ""
	}
	rest := html[i+len(open):]
	j := strings.IndexByte(rest, '"')
	if j < 0 {
		return ""
	}
	return rest[:j]
}

func guestTestGetenv(t *testing.T, secret string) func(string) string {
	t.Helper()
	t.Setenv("UBYHOST_SECRET_KEY", secret)
	t.Setenv("UBYHOST_GUEST_PIN", "0")
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	return func(k string) string {
		if v := os.Getenv(k); v != "" {
			return v
		}
		return ""
	}
}

func csrfCookie(cookies []*http.Cookie) string {
	for _, c := range cookies {
		if c.Name == "ubyhost_csrf" {
			return c.Value
		}
	}
	return ""
}

func TestGuestFormCSRFRoundTrip(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	secret := strings.Repeat("s", 32)
	getenv := guestTestGetenv(t, secret)
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	ctx := t.Context()
	stamp := "2026-01-01T00:00:00Z"

	mux := http.NewServeMux()
	RegisterStayClaim(mux, pool, getenv, now, func(_ string, h http.HandlerFunc) http.Handler { return h }, nil)
	RegisterParty(mux, pool, getenv, now, func(_ string, h http.HandlerFunc) http.Handler { return h })

	type claimState string
	states := []struct {
		name    string
		state   claimState
		getPath func(tok string, resID int64) string
	}{
		{"unclaimed", claimStateUnclaimed, func(tok string, resID int64) string {
			return fmt.Sprintf("/l/%s/%d?lang=en", tok, resID)
		}},
		{"claimed", claimStateClaimed, func(tok string, resID int64) string {
			// Claimed stays no longer show the party form on overview; claim confirm still mints CSRF.
			return fmt.Sprintf("/l/%s/%d/claim?lang=en", tok, resID)
		}},
	}

	for _, st := range states {
		t.Run("party_"+st.name, func(t *testing.T) {
			aptID := time.Now().UnixNano()%8000000000 + 5000000
			userID := aptID
			resID := aptID + 1
			tok := fmt.Sprintf("csrftok%d", aptID)
			mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
				VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("u%d@example.test", aptID), stamp)
			mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
				VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4)`, aptID, userID, tok, stamp)
			slug := fmt.Sprintf("party-%d-abc234", aptID)
			mustExecGuest(t, ctx, pool, `INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at)
				VALUES ($1, $2, 1, $3)`, slug, aptID, stamp)
			mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
				VALUES ($1, $2, $3, 'active', 'manual', $4, $5, $6, $6)`, resID, aptID, fmt.Sprintf("stay-%d", resID), "2026-06-10", "2026-06-12", stamp)
			mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
				VALUES ($1, $2, '', 1, $3, $3) ON CONFLICT (reservation_id) DO UPDATE SET state = EXCLUDED.state`, resID, string(st.state), stamp)

			getPath := st.getPath(slug, resID)
			getReq := httptest.NewRequest(http.MethodGet, getPath, nil)
			getRec := httptest.NewRecorder()
			mux.ServeHTTP(getRec, getReq)
			if getRec.Code != http.StatusOK {
				t.Fatalf("GET %s status %d body %q", getPath, getRec.Code, getRec.Body.String()[:min(200, getRec.Body.Len())])
			}
			csrf := extractPageCSRF(getRec.Body.String())
			if csrf == "" || csrf == "*" {
				t.Fatalf("GET page csrf %q", csrf)
			}
			cookie := csrfCookie(getRec.Result().Cookies())
			if cookie == "" {
				t.Fatal("missing ubyhost_csrf cookie")
			}

			for _, key := range []string{slug, tok} {
				postPath := fmt.Sprintf("/l/%s/%d/party?lang=en", key, resID)
				postBody := url.Values{"_csrf": {csrf}, "party_size": {"2"}}
				postReq := httptest.NewRequest(http.MethodPost, postPath, strings.NewReader(postBody.Encode()))
				postReq.Header.Set("Content-Type", "application/x-www-form-urlencoded")
				postReq.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: cookie})
				postRec := httptest.NewRecorder()
				mux.ServeHTTP(postRec, postReq)
				if postRec.Code != http.StatusSeeOther {
					t.Fatalf("party POST did not redirect: status %d", postRec.Code)
				}
				if location := postRec.Header().Get("Location"); !strings.HasPrefix(location, fmt.Sprintf("/l/%s/%d", key, resID)) {
					t.Fatal("party POST did not redirect to the same guest stay")
				}
			}
		})
	}

	t.Run("claim_confirm", func(t *testing.T) {
		aptID := time.Now().UnixNano()%8000000000 + 6000000
		userID := aptID
		resID := aptID + 2
		tok := fmt.Sprintf("claimcsrf%d", aptID)
		mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
			VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("c%d@example.test", aptID), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
			VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4)`, aptID, userID, tok, stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
			VALUES ($1, $2, $3, 'active', 'manual', $4, $5, $6, $6)`, resID, aptID, fmt.Sprintf("stay-%d", resID), "2026-06-10", "2026-06-12", stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
			VALUES ($1, $2, '', 1, $3, $3) ON CONFLICT DO NOTHING`, resID, claimStateUnclaimed, stamp)

		getPath := fmt.Sprintf("/l/%s/%d/claim?lang=en", tok, resID)
		getReq := httptest.NewRequest(http.MethodGet, getPath, nil)
		getRec := httptest.NewRecorder()
		mux.ServeHTTP(getRec, getReq)
		if getRec.Code != http.StatusOK {
			t.Fatalf("GET %s status %d", getPath, getRec.Code)
		}
		csrf := extractPageCSRF(getRec.Body.String())
		if csrf == "" || csrf == "*" {
			t.Fatalf("confirm csrf %q", csrf)
		}
		cookie := csrfCookie(getRec.Result().Cookies())
		if cookie == "" {
			t.Fatal("missing ubyhost_csrf cookie")
		}

		postPath := fmt.Sprintf("/l/%s/%d/claim/confirm?lang=en", tok, resID)
		postBody := url.Values{"_csrf": {csrf}, "secret": {"not-the-real-secret"}}
		postReq := httptest.NewRequest(http.MethodPost, postPath, strings.NewReader(postBody.Encode()))
		postReq.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		postReq.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: cookie})
		postRec := httptest.NewRecorder()
		mux.ServeHTTP(postRec, postReq)
		respBody, _ := io.ReadAll(postRec.Body)
		if postRec.Code == http.StatusForbidden && strings.Contains(string(respBody), "Cross-site") {
			t.Fatalf("POST claim/confirm rejected CSRF: %s", respBody)
		}
	})
}
