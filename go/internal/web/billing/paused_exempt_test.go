package billingweb

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// TestLoginPausedExemptions checks hostweb.Login on a paused plan: the
// read-only-open paths still POST (as Python's require_login allows), other
// POSTs redirect to the plan page, and GET is never redirected.
func TestLoginPausedExemptions(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	seedAccount(t, pool, 1, "paused", "standard", "month")
	env := testEnvMap(nil)
	h := func(w http.ResponseWriter, r *http.Request) {
		host, err := hostweb.Login(w, r, pool, env, testNow)
		if err != nil {
			t.Errorf("Login error: %v", err)
			return
		}
		if host != nil {
			w.WriteHeader(http.StatusNoContent)
		}
	}
	send := func(who, method, path string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(method, path, nil)
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor(who, testNow)})
		rec := httptest.NewRecorder()
		http.HandlerFunc(h).ServeHTTP(rec, req)
		return rec
	}

	exempt := []string{
		"/account/logout-all",
		"/settings/privacy/ad-consent",
		"/predplatne/obnovit",
		"/logout",
		"/exports/x",
		"/reservations/5/submit",
		"/guests/5/resend",
	}
	for _, p := range exempt {
		t.Run("exempt POST "+p, func(t *testing.T) {
			if rec := send("host1", http.MethodPost, p); rec.Code != http.StatusNoContent {
				t.Errorf("%s: %d %s", p, rec.Code, rec.Header().Get("Location"))
			}
		})
	}

	for _, p := range []string{"/apartments", "/reservations/5"} {
		t.Run("paused POST "+p, func(t *testing.T) {
			rec := send("host1", http.MethodPost, p)
			if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/predplatne?paused=1" {
				t.Errorf("%s: %d %s", p, rec.Code, rec.Header().Get("Location"))
			}
		})
	}

	t.Run("paused GET /apartments", func(t *testing.T) {
		if rec := send("host1", http.MethodGet, "/apartments"); rec.Code != http.StatusNoContent {
			t.Errorf("GET /apartments: %d %s", rec.Code, rec.Header().Get("Location"))
		}
	})

	t.Run("impersonating admin POST /apartments", func(t *testing.T) {
		if rec := send("admin_imp", http.MethodPost, "/apartments"); rec.Code != http.StatusNoContent {
			t.Errorf("admin_imp POST /apartments: %d %s", rec.Code, rec.Header().Get("Location"))
		}
	})

	t.Run("active plan POST /apartments", func(t *testing.T) {
		if _, err := pool.Exec(context.Background(), `UPDATE billing_account SET status = 'active' WHERE owner_user_id = 1`); err != nil {
			t.Fatal(err)
		}
		if rec := send("host1", http.MethodPost, "/apartments"); rec.Code != http.StatusNoContent {
			t.Errorf("active POST /apartments: %d %s", rec.Code, rec.Header().Get("Location"))
		}
	})
}
