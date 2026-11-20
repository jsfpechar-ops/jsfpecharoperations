package public

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type utilityGolden struct {
	PublicBaseURL string `json:"public_base_url"`
	Seed          []struct {
		Table   string   `json:"table"`
		Columns []string `json:"columns"`
		Rows    [][]any  `json:"rows"`
	} `json:"seed"`
	Cases []struct {
		Name       string            `json:"name"`
		Method     string            `json:"method"`
		Path       string            `json:"path"`
		Status     int               `json:"status"`
		Headers    map[string]string `json:"headers"`
		SetCookies []map[string]any  `json:"set_cookies"`
		Body       string            `json:"body"`
	} `json:"cases"`
}

func loadUtilityGolden(t *testing.T) utilityGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/utility_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g utilityGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func seedUtility(t *testing.T, pool *pgxpool.Pool, g utilityGolden) {
	t.Helper()
	ctx := context.Background()
	for _, block := range g.Seed {
		cols := strings.Join(block.Columns, ", ")
		for i := range block.Rows {
			ph := make([]string, len(block.Columns))
			args := make([]any, len(block.Columns))
			for j, v := range block.Rows[i] {
				ph[j] = fmt.Sprintf("$%d", j+1)
				args[j] = v
			}
			q := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", block.Table, cols, strings.Join(ph, ", "))
			if _, err := pool.Exec(ctx, q, args...); err != nil {
				t.Fatalf("%s: %v", block.Table, err)
			}
		}
	}
}

func utilityMux(pool *pgxpool.Pool, getenv func(string) string) *http.ServeMux {
	mux := http.NewServeMux()
	RegisterUtility(mux, DepsUtility{Getenv: getenv, Pool: pool, Now: func() time.Time {
		return time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	}}, func(_ string, h http.HandlerFunc) http.Handler { return h })
	return mux
}

func getenvGolden(k string) string {
	if k == "UBYHOST_SECRET_KEY" {
		return "utility-golden-secret-not-real-0123456789"
	}
	if k == "UBYHOST_PUBLIC_BASE_URL" {
		return "https://golden.example.test"
	}
	if k == "UBYHOST_DEPLOYMENT" {
		return "local"
	}
	if k == "UBYHOST_APP_ROOT" {
		return "../../../../App/app"
	}
	return os.Getenv(k)
}

func parseSetCookies(h http.Header) []map[string]any {
	var out []map[string]any
	for _, line := range h.Values("Set-Cookie") {
		parts := strings.Split(line, ";")
		name, val, _ := strings.Cut(strings.TrimSpace(parts[0]), "=")
		entry := map[string]any{
			"name": name, "value": val, "path": "", "max_age": "", "samesite": "", "secure": false, "httponly": false,
		}
		for _, p := range parts[1:] {
			p = strings.TrimSpace(p)
			key, v, _ := strings.Cut(p, "=")
			switch strings.ToLower(key) {
			case "path":
				entry["path"] = v
			case "max-age":
				entry["max_age"] = v
			case "samesite":
				entry["samesite"] = strings.ToLower(v)
			case "secure":
				entry["secure"] = true
			case "httponly":
				entry["httponly"] = true
			}
		}
		out = append(out, entry)
	}
	return out
}

func headerSubset(got http.Header, want map[string]string) {
	for k, v := range want {
		if got.Get(k) != v {
			panic(fmt.Sprintf("header %q got %q want %q", k, got.Get(k), v))
		}
	}
}

var csrfMeta = regexp.MustCompile(`name="csrf-token" content="([^"]+)"`)

func TestUtilityGolden(t *testing.T) {
	g := loadUtilityGolden(t)
	pool := unsubTestPool(t)
	seedUtility(t, pool, g)
	mux := utilityMux(pool, getenvGolden)

	var csrf string
	warm := httptest.NewRecorder()
	mux.ServeHTTP(warm, httptest.NewRequest(http.MethodGet, "https://golden.example.test/login?lang=en", nil))
	if m := csrfMeta.FindStringSubmatch(warm.Body.String()); m != nil {
		csrf = m[1]
	}

	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			var body io.Reader
			reqURL := "https://golden.example.test" + c.Path
			req, err := http.NewRequest(c.Method, reqURL, body)
			if err != nil {
				t.Fatal(err)
			}
			if c.Method == http.MethodPost {
				form := url.Values{"lang": {"cs"}, "next": {"/login?lang=en"}, "_csrf": {csrf}}
				if c.Name != "post-language-cs" {
					form = url.Values{}
				}
				req, _ = http.NewRequest(http.MethodPost, "https://golden.example.test"+c.Path, strings.NewReader(form.Encode()))
				req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
				req.Header.Set("X-Csrf-Token", csrf)
			}
			rec := httptest.NewRecorder()
			mux.ServeHTTP(rec, req)
			if rec.Code != c.Status {
				t.Fatalf("status %d want %d", rec.Code, c.Status)
			}
			defer func() {
				if r := recover(); r != nil {
					t.Fatal(r)
				}
			}()
			headerSubset(rec.Header(), c.Headers)
			if c.Method == http.MethodGet && rec.Body.String() != c.Body {
				t.Fatalf("body mismatch len got %d want %d", len(rec.Body.String()), len(c.Body))
			}
			if len(c.SetCookies) > 0 {
				got := parseSetCookies(rec.Header())
				if len(got) != len(c.SetCookies) {
					t.Fatalf("set-cookie count %d want %d", len(got), len(c.SetCookies))
				}
				for i, want := range c.SetCookies {
					for k, v := range want {
						if fmt.Sprint(got[i][k]) != fmt.Sprint(v) {
							t.Fatalf("cookie %d %s got %v want %v", i, k, got[i][k], v)
						}
					}
				}
			}
		})
	}
}

func TestUtilityGoldenStaticWithoutDB(t *testing.T) {
	if os.Getenv("UBYHOST_TEST_DATABASE_URL") != "" {
		t.Skip("covered by TestUtilityGolden")
	}
	g := loadUtilityGolden(t)
	mux := utilityMux(nil, getenvGolden)
	for _, c := range g.Cases {
		if c.Name == "sitemap" || c.Name == "post-language-cs" {
			continue
		}
		t.Run(c.Name, func(t *testing.T) {
			rec := httptest.NewRecorder()
			req := httptest.NewRequest(c.Method, "https://golden.example.test"+c.Path, nil)
			mux.ServeHTTP(rec, req)
			if rec.Code != c.Status {
				t.Fatalf("status %d want %d", rec.Code, c.Status)
			}
			if rec.Body.String() != c.Body && c.Body != "" {
				t.Fatalf("body mismatch for %s", c.Name)
			}
		})
	}
}
