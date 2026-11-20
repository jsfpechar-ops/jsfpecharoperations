package submissions

import (
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

func detailGET(t *testing.T, mux http.Handler, now time.Time, ownerID int64, path string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	if ownerID != 0 {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, map[string]any{
			"uid": ownerID, "sv": 1,
		}, now)})
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func TestSubmissionDetailUnauthorizedRedirectsLogin(t *testing.T) {
	pool := dbPool(t)
	now := time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC)
	mux := http.NewServeMux()
	Register(mux, pool, testGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	rec := detailGET(t, mux, now, 0, "/submissions/1")
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/submissions/1" {
		t.Fatalf("unsigned: code=%d loc=%q", rec.Code, rec.Header().Get("Location"))
	}
}

func TestSubmissionDetailNonNumericIDNotFound(t *testing.T) {
	pool := dbPool(t)
	now := time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC)
	ownerID, _, _ := seedParityWorld(t, pool, now)
	mux := http.NewServeMux()
	Register(mux, pool, testGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	rec := detailGET(t, mux, now, ownerID, "/submissions/not-an-id")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("code %d, want 404", rec.Code)
	}
}

func TestSubmissionDetailMissingOrForeignRedirects(t *testing.T) {
	pool := dbPool(t)
	ctx := t.Context()
	now := time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC)
	ownerID, okID, _ := seedParityWorld(t, pool, now)
	stamp := now.UTC().Format(time.RFC3339)
	var otherID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at, email)
		VALUES ('reports-other', 'x', 'host', 1, 1, $1, 'other@example.test') RETURNING id`, stamp).Scan(&otherID); err != nil {
		t.Fatal(err)
	}
	seedLegalAcceptance(t, pool, otherID, now)
	mux := http.NewServeMux()
	Register(mux, pool, testGetenv, func() time.Time { return now },
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	cases := []struct {
		name string
		uid  int64
		path string
	}{
		{"missing", ownerID, "/submissions/99999999"},
		{"foreign", otherID, "/submissions/" + strconv.FormatInt(okID, 10)},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			rec := detailGET(t, mux, now, c.uid, c.path)
			if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/submissions" {
				t.Fatalf("code=%d loc=%q", rec.Code, rec.Header().Get("Location"))
			}
		})
	}
}