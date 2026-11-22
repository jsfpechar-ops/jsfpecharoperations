package public

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/auth/authpage"
)

// offlineHandler for a request, as the mux wires it.
func offlineRequest(t *testing.T, target string, cookies ...*http.Cookie) *httptest.ResponseRecorder {
	t.Helper()
	mux := http.NewServeMux()
	RegisterUtility(mux, DepsUtility{Getenv: func(string) string { return "" }, Now: time.Now},
		func(_ string, h http.HandlerFunc) http.Handler { return h })
	req := httptest.NewRequest(http.MethodGet, target, nil)
	for _, c := range cookies {
		req.AddCookie(c)
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

// A visitor gets Czech (PUBLIC_DEFAULT_LANGUAGE) whatever the browser prefers,
// a ?lang= link wins, then the ubyhost_lang cookie — host_i18n.resolve_language.
func TestOfflineLanguageVisitor(t *testing.T) {
	cases := []struct {
		name, target string
		cookie       *http.Cookie
		want         string
	}{
		{"visitor default", "/offline", nil, "cs"},
		{"accept-language ignored", "/offline", nil, "cs"},
		{"query wins", "/offline?lang=en", nil, "en"},
		{"cookie wins", "/offline", &http.Cookie{Name: langCookieName, Value: "vi"}, "vi"},
		{"query beats cookie", "/offline?lang=en", &http.Cookie{Name: langCookieName, Value: "vi"}, "en"},
		{"unsupported falls back", "/offline?lang=de", &http.Cookie{Name: langCookieName, Value: "de"}, "cs"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			var cookies []*http.Cookie
			if tc.cookie != nil {
				cookies = append(cookies, tc.cookie)
			}
			rec := offlineRequest(t, tc.target, cookies...)
			if rec.Code != http.StatusOK {
				t.Fatalf("status %d", rec.Code)
			}
			if got := rec.Header().Get("Content-Language"); got != tc.want {
				t.Fatalf("Content-Language %q, want %q", got, tc.want)
			}
		})
	}
}

// A session cookie that does not load (no pool here, so none can) stays a
// visitor: the page is served offline, and a broken cookie must not 500 it.
func TestOfflineLanguageStaleSessionIsVisitor(t *testing.T) {
	rec := offlineRequest(t, "/offline", &http.Cookie{Name: "ubyhost_session", Value: "not-a-session"})
	if rec.Code != http.StatusOK || rec.Header().Get("Content-Language") != "cs" {
		t.Fatalf("status %d lang %q", rec.Code, rec.Header().Get("Content-Language"))
	}
}

// The signed-in fallback is English, which is what makes /offline match Python
// for a host (templating.render: DEFAULT_LANGUAGE when current_user is set).
func TestOfflineSignedInFallbackIsEnglish(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/offline", nil)
	if got := authpage.Language(req, true); got != "en" {
		t.Fatalf("signed-in fallback %q, want en", got)
	}
	if got := authpage.Language(req, false); got != "cs" {
		t.Fatalf("visitor fallback %q, want cs", got)
	}
}
