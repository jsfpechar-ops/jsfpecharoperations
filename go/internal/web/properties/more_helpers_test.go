package properties

// Test helpers for the briefs 1520 and later (no golden file: the cases are
// written out and each names the Python line it mirrors).

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const stamp0 = "2026-01-01T00:00:00+00:00"

// moreEnv is testEnv plus the door-code switch and the TTLock app keys.
func moreEnv(extra map[string]string) func(string) string {
	return func(k string) string {
		if v, ok := extra[k]; ok {
			return v
		}
		return testEnv(k)
	}
}

func mustExec(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatalf("%s: %v", sql, err)
	}
}

// seedHosts adds hosts 130001 and 130002, admin 130003 and accepted legal terms.
func seedHosts(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	for _, u := range []struct {
		id         int64
		name, role string
	}{{130001, "props-host-a", "host"}, {130002, "props-host-b", "host"}, {130003, "props-admin", "admin"}} {
		mustExec(t, pool, `INSERT INTO user_account (id, username, password_hash, role, active, must_change_password, session_version, created_at)
			VALUES ($1, $2, 'x', $3, 1, 0, 1, $4)`, u.id, u.name, u.role, stamp0)
		for j, doc := range []struct{ name, version string }{{"terms", "t1"}, {"privacy", "p1"}, {"dpa", "d1"}} {
			mustExec(t, pool, `INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method)
				VALUES ($1, $2, $3, $4, NOW(), 'clickwrap')`, u.id*10+int64(j), u.id, doc.name, doc.version)
		}
	}
}

// getAs sends a GET as host uid (0 is signed out; as > 0 is that admin acting
// inside workspace as), with extra headers.
func getAs(t *testing.T, mux http.Handler, path string, uid, as int64, hdr map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "en"})
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	if uid != 0 {
		payload := map[string]any{"uid": uid, "sv": int64(1), "iat": testNow.Unix()}
		if as != 0 {
			payload["as"] = as
			payload["ast"] = testNow.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

// postAs is post with extra request headers.
func postAs(t *testing.T, mux http.Handler, path string, uid int64, form map[string]string, hdr map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	values := map[string][]string{}
	for k, v := range form {
		values[k] = []string{v}
	}
	if len(hdr) == 0 {
		return post(t, mux, path, uid, 0, "en", values)
	}
	body := "_csrf=" + csrfToken(t, csrfCookie)
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfCookie})
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "en"})
	payload := map[string]any{"uid": uid, "sv": int64(1), "iat": testNow.Unix()}
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func noWrap(_ string, h http.HandlerFunc) http.Handler { return h }

func oneInt(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) int64 {
	t.Helper()
	var n int64
	if err := pool.QueryRow(context.Background(), sql, args...).Scan(&n); err != nil {
		t.Fatalf("%s: %v", sql, err)
	}
	return n
}

// postWithHost is postAs with the request Host set.
func postWithHost(t *testing.T, mux http.Handler, path string, uid int64, host string, hdr map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	body := "_csrf=" + csrfToken(t, csrfCookie)
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(body))
	req.Host = host
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfCookie})
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "en"})
	if uid != 0 {
		payload := map[string]any{"uid": uid, "sv": int64(1), "iat": testNow.Unix()}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}
