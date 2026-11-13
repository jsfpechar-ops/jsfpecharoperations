package auth

import (
	"bufio"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

// TestRoutesBuildWithoutPool: the route list must not touch the pool.
func TestRoutesBuildWithoutPool(t *testing.T) {
	seen := map[string]bool{}
	for _, r := range Routes(nil, func(string) string { return "" }, time.Now) {
		if r.Handler == nil || seen[r.Pattern] || r.Pattern == "GET /" {
			t.Errorf("bad route %q", r.Pattern)
		}
		seen[r.Pattern] = true
	}
	if len(seen) != 18 {
		t.Errorf("%d routes, want 18", len(seen))
	}
}

// TestCatalogHasEveryKey: every key in i18n_keys.txt has en and cs text (vi
// may miss one; T falls back to en, as host_i18n.translate does).
func TestCatalogHasEveryKey(t *testing.T) {
	f, err := os.Open("i18n_keys.txt")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	s := bufio.NewScanner(f)
	for s.Scan() {
		key := strings.TrimSpace(s.Text())
		if key == "" || strings.HasPrefix(key, "#") {
			continue
		}
		for _, lang := range []string{"en", "cs"} {
			if catalog[lang][key] == "" {
				t.Errorf("%s has no %s text", key, lang)
			}
		}
	}
}

func TestSupportReasonAndPathID(t *testing.T) {
	for in, want := range map[string]string{"  needs\n help\x1cnow ": "needs help now", "abc": "", " a b c ": "a b c", strings.Repeat("x", 301): ""} {
		if got := supportReason(in); got != want {
			t.Errorf("supportReason(%q) = %q, want %q", in, got, want)
		}
	}
	mux := http.NewServeMux()
	mux.HandleFunc("POST /x/{id}", func(w http.ResponseWriter, r *http.Request) {
		if id, ok := pathID(w, r, "user_id"); ok {
			w.Header().Set("X-ID", itoa(id))
		}
	})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("POST", "/x/a%3Cb", nil))
	want := `{"detail":[{"type":"int_parsing","loc":["path","user_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"a<b"}]}`
	if rec.Code != 422 || rec.Body.String() != want {
		t.Errorf("422: %d %s", rec.Code, rec.Body.String())
	}
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("POST", "/x/42", nil))
	if rec.Header().Get("X-ID") != "42" {
		t.Errorf("id 42 not parsed")
	}
}
