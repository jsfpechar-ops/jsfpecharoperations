package turnstile

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"reflect"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"
)

type golden struct {
	Env []struct {
		Env        map[string]string `json:"env"`
		Required   bool              `json:"required"`
		Enabled    bool              `json:"enabled"`
		SiteKey    string            `json:"site_key"`
		Secret     string            `json:"secret"`
		Hostnames  []string          `json:"hostnames"`
		Deployment string            `json:"deployment"`
	} `json:"env"`
	Verify []struct {
		Name   string          `json:"name"`
		Token  string          `json:"token"`
		Status json.RawMessage `json:"status"`
		Body   *string         `json:"body"`
		Result json.RawMessage `json:"result"`
		Posted *struct {
			URL     string            `json:"url"`
			Data    map[string]string `json:"data"`
			Timeout int               `json:"timeout"`
		} `json:"posted"`
	} `json:"verify"`
	VerifyURL   string   `json:"verify_url"`
	Hostnames   []string `json:"hostnames"`
	Secret      string   `json:"secret"`
	RemoteIP    string   `json:"remoteip"`
	Unreachable struct {
		Max    int `json:"max"`
		Window int `json:"window"`
	} `json:"unreachable"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/turnstile.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Env) == 0 || len(g.Verify) == 0 {
		t.Fatal("empty golden")
	}
	return g
}

func envOf(m map[string]string) func(string) string { return func(k string) string { return m[k] } }

// TestConfigMatchesPython: config.py's TURNSTILE_* parsing and required().
func TestConfigMatchesPython(t *testing.T) {
	g := loadGolden(t)
	if VerifyURL != g.VerifyURL || Timeout != 10*time.Second ||
		unreachableMax != g.Unreachable.Max || unreachableWindow != g.Unreachable.Window {
		t.Fatalf("constants differ from turnstile.py")
	}
	for _, c := range g.Env {
		cfg := FromEnv(envOf(c.Env))
		var hosts []string
		for h := range cfg.Hostnames {
			hosts = append(hosts, h)
		}
		sort.Strings(hosts)
		if hosts == nil {
			hosts = []string{}
		}
		if cfg.Required() != c.Required || cfg.Enabled() != c.Enabled || cfg.SiteKey != c.SiteKey ||
			cfg.Secret != c.Secret || cfg.Deployment != c.Deployment || !reflect.DeepEqual(hosts, c.Hostnames) {
			t.Errorf("env %v: got %+v required=%v enabled=%v", c.Env, cfg, cfg.Required(), cfg.Enabled())
		}
		want := ""
		if c.Enabled {
			want = c.SiteKey
		}
		if PageSiteKey(envOf(c.Env)) != want || Required(envOf(c.Env)) != c.Required {
			t.Errorf("env %v: PageSiteKey or Required differ", c.Env)
		}
	}
}

func verifyEnv(g golden) func(string) string {
	return envOf(map[string]string{
		"UBYHOST_DEPLOYMENT":  "production",
		"TURNSTILE_SECRET":    g.Secret,
		"TURNSTILE_HOSTNAMES": strings.Join(g.Hostnames, ","),
	})
}

// TestVerifyMatchesPython runs every verify case of the golden against a fake
// siteverify server: the same form fields, the same answer. The fail-open
// cases (Python's _fail_open) are checked to be "unreachable" here and end to
// end in TestFailOpenBudget.
func TestVerifyMatchesPython(t *testing.T) {
	g := loadGolden(t)
	for _, c := range g.Verify {
		t.Run(c.Name, func(t *testing.T) {
			var mu sync.Mutex
			var gotBody, gotType string
			calls := 0
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				b, _ := io.ReadAll(r.Body)
				mu.Lock()
				calls++
				gotBody, gotType = string(b), r.Header.Get("Content-Type")
				mu.Unlock()
				switch string(c.Status) {
				case "null":
					time.Sleep(300 * time.Millisecond)
					return
				case `"connection"`:
					hj, _ := w.(http.Hijacker)
					conn, _, _ := hj.Hijack()
					conn.Close()
					return
				}
				var status int
				_ = json.Unmarshal(c.Status, &status)
				w.WriteHeader(status)
				_, _ = io.WriteString(w, *c.Body)
			}))
			defer srv.Close()
			v := Verifier{Getenv: verifyEnv(g), URL: srv.URL, Client: &http.Client{Timeout: 100 * time.Millisecond}}
			r := httptest.NewRequest("POST", "/login", nil)
			r.RemoteAddr = g.RemoteIP + ":1234"
			cfg := FromEnv(v.Getenv)
			var got string
			if c.Token == "" || len([]rune(c.Token)) > maxToken {
				ok, err := v.Verify(context.Background(), r, c.Token, "host_login")
				if err != nil {
					t.Fatal(err)
				}
				got = map[bool]string{true: "true", false: "false"}[ok]
			} else {
				result, err := v.siteverify(context.Background(), cfg.Secret, c.Token, g.RemoteIP)
				switch {
				case errors.Is(err, errUnreachable):
					got = `"fail_open"`
				case err != nil:
					t.Fatal(err)
				default:
					got = map[bool]string{true: "true", false: "false"}[Accepted(result, "host_login", cfg.Hostnames)]
				}
			}
			if got != string(c.Result) {
				t.Fatalf("result %s, want %s", got, c.Result)
			}
			mu.Lock()
			defer mu.Unlock()
			if c.Posted == nil {
				if calls != 0 {
					t.Fatalf("posted %d times, Python posts nothing", calls)
				}
				return
			}
			if calls != 1 || gotType != "application/x-www-form-urlencoded" {
				t.Fatalf("calls=%d type=%q", calls, gotType)
			}
			order := []string{}
			for _, part := range strings.Split(gotBody, "&") {
				order = append(order, strings.SplitN(part, "=", 2)[0])
			}
			form, err := url.ParseQuery(gotBody)
			if err != nil || !reflect.DeepEqual(order, []string{"secret", "response", "remoteip"}) {
				t.Fatalf("form %q", gotBody)
			}
			for k, want := range c.Posted.Data {
				if form.Get(k) != want {
					t.Fatalf("field %s differs", k)
				}
			}
		})
	}
}

// TestSkippedWhenNotRequired: outside production, or without secret or
// hostnames, Verify passes without a request (turnstile.required()).
func TestSkippedWhenNotRequired(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("siteverify was called")
	}))
	defer srv.Close()
	for _, env := range []map[string]string{
		{},
		{"UBYHOST_DEPLOYMENT": "staging", "TURNSTILE_SECRET": "s", "TURNSTILE_HOSTNAMES": "a.com"},
		{"UBYHOST_DEPLOYMENT": "production", "TURNSTILE_HOSTNAMES": "a.com"},
		{"UBYHOST_DEPLOYMENT": "production", "TURNSTILE_SECRET": "s"},
	} {
		v := Verifier{Getenv: envOf(env), URL: srv.URL}
		ok, err := v.Verify(context.Background(), httptest.NewRequest("POST", "/login", nil), "", "host_login")
		if !ok || err != nil {
			t.Errorf("env %v: %v %v, want pass", env, ok, err)
		}
	}
}

// TestNonObjectAnswerIsAnError: a JSON answer that is not an object raises
// AttributeError in Python (HTTP 500); Go returns an error.
func TestNonObjectAnswerIsAnError(t *testing.T) {
	for _, body := range []string{`[1]`, `null`, `"x"`} {
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			_, _ = io.WriteString(w, body)
		}))
		g := loadGolden(t)
		v := Verifier{Getenv: verifyEnv(g), URL: srv.URL}
		r := httptest.NewRequest("POST", "/login", nil)
		ok, err := v.Verify(context.Background(), r, "tok", "host_login")
		srv.Close()
		if ok || err == nil || errors.Is(err, errUnreachable) {
			t.Errorf("body %s: %v %v, want an error", body, ok, err)
		}
	}
}
