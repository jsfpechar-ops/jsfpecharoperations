package auth

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

type exportGolden struct {
	Secret string            `json:"secret"`
	Nonce  string            `json:"nonce"`
	Env    map[string]string `json:"env"`
	Fixed  string            `json:"fixed"`
	Seed   [][2]any          `json:"seed"`
	Cases  []exportCase      `json:"cases"`
}

type exportWant struct {
	Status             int                    `json:"status"`
	Location           *string                `json:"location"`
	ContentType        *string                `json:"content_type"`
	CacheControl       *string                `json:"cache_control"`
	ContentDisposition *string                `json:"content_disposition"`
	Body               *string                `json:"body"`
	ZipNames           []string               `json:"zip_names"`
	Manifest           map[string]any         `json:"manifest"`
	Cookies            []cookieRec            `json:"cookies"`
	DB                 map[string][][]*string `json:"db"`
}

type exportCase struct {
	Name    string            `json:"name"`
	Method  string            `json:"method"`
	Path    string            `json:"path"`
	Session map[string]int64  `json:"session"`
	CSRF    *bool             `json:"csrf"`
	Lang    string            `json:"lang"`
	Headers map[string]string `json:"headers"`
	Form    [][2]string       `json:"form"`
	Seed    [][2]any          `json:"seed"`
	Env     map[string]string `json:"env"`
	Want    exportWant        `json:"want"`
}

var exportWatch = map[string]string{
	"audit": `SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id`,
}

func emptyHeader(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func exportDump(t *testing.T, ctx context.Context, pool *pgxpool.Pool) map[string][][]*string {
	t.Helper()
	out := map[string][][]*string{}
	for name, sql := range exportWatch {
		rows, err := pool.Query(ctx, sql)
		if err != nil {
			t.Fatal(err)
		}
		out[name] = [][]*string{}
		for rows.Next() {
			vals, err := rows.Values()
			if err != nil {
				t.Fatal(err)
			}
			row := make([]*string, len(vals))
			for i, v := range vals {
				row[i] = norm(v)
			}
			out[name] = append(out[name], row)
		}
		rows.Close()
	}
	return out
}

func TestWorkspaceExportRouteListed(t *testing.T) {
	n := 0
	for _, r := range Routes(nil, func(string) string { return "" }, time.Now) {
		if r.Pattern == "POST /admin/users/{id}/export" {
			n++
			if r.Path != "/admin/users/{id}/export" {
				t.Errorf("label %q", r.Path)
			}
		}
	}
	if n != 1 {
		t.Fatalf("route listed %d times, want 1", n)
	}
	mux := http.NewServeMux()
	for _, r := range Routes(nil, func(string) string { return "" }, time.Now) {
		mux.Handle(r.Pattern, r.Handler)
	}
}

func TestWorkspaceExportGoldenDatabase(t *testing.T) {
	raw, err := os.ReadFile("testdata/workspace_export.json")
	if err != nil {
		t.Fatal(err)
	}
	var g exportGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	fixed, err := time.Parse(time.RFC3339Nano, g.Fixed)
	if err != nil {
		t.Fatal(err)
	}
	clock := func() time.Time { return fixed }
	pool := testPool(t)
	ctx := context.Background()
	sum := sha256.Sum256([]byte(g.Nonce))
	csrfToken, err := secure.NewTimedSerializer(g.Secret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, fixed)
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			loadSeed(t, ctx, pool, append(append([][2]any{}, g.Seed...), c.Seed...), fixed)
			env := map[string]string{}
			for k, v := range g.Env {
				env[k] = v
			}
			for k, v := range c.Env {
				env[k] = v
			}
			getenv := func(k string) string { return env[k] }
			mux := http.NewServeMux()
			for _, r := range Routes(pool, getenv, clock) {
				h := r.Handler
				mux.Handle(r.Pattern, http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
					w.Header().Set("Cache-Control", "no-store, private")
					h(w, req)
				}))
			}
			csrf := c.CSRF == nil || *c.CSRF
			var pairs []string
			for _, p := range c.Form {
				pairs = append(pairs, url.QueryEscape(p[0])+"="+url.QueryEscape(p[1]))
			}
			if csrf && c.Method == http.MethodPost {
				pairs = append(pairs, "_csrf="+url.QueryEscape(csrfToken))
			}
			req := httptest.NewRequest(c.Method, "http://testserver"+c.Path, strings.NewReader(strings.Join(pairs, "&")))
			req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
			var cookies []string
			if c.Session != nil {
				cookies = append(cookies, "ubyhost_session="+sessionToken(t, g.Secret, c.Session, fixed))
			}
			if csrf {
				cookies = append(cookies, "ubyhost_csrf="+g.Nonce)
			}
			if c.Lang != "" {
				cookies = append(cookies, "ubyhost_lang="+c.Lang)
			}
			if len(cookies) > 0 {
				req.Header.Set("Cookie", strings.Join(cookies, "; "))
			}
			for k, v := range c.Headers {
				req.Header.Set(k, v)
			}
			rec := httptest.NewRecorder()
			mux.ServeHTTP(rec, req)
			res := rec.Result()
			w := c.Want
			if res.StatusCode != w.Status {
				t.Fatalf("status %d, want %d (body %q)", res.StatusCode, w.Status, rec.Body.String())
			}
			for _, h := range []struct {
				name string
				want *string
			}{{"Location", w.Location}, {"Content-Type", w.ContentType}, {"Cache-Control", w.CacheControl},
				{"Content-Disposition", w.ContentDisposition}} {
				got := header(res.Header, h.name)
				if emptyHeader(got) != emptyHeader(h.want) {
					t.Errorf("%s %q, want %q", h.name, emptyHeader(got), emptyHeader(h.want))
				}
			}
			if w.Body != nil && rec.Body.String() != *w.Body {
				t.Errorf("body %q, want %q", rec.Body.String(), *w.Body)
			}
			var gotCookies []cookieRec
			for _, line := range res.Header["Set-Cookie"] {
				gotCookies = append(gotCookies, parseCookie(t, g.Secret, line, fixed))
			}
			if len(gotCookies) != len(w.Cookies) {
				t.Fatalf("cookies %+v, want %+v", gotCookies, w.Cookies)
			}
			for i := range gotCookies {
				if gotCookies[i].Name != w.Cookies[i].Name || gotCookies[i].Empty != w.Cookies[i].Empty ||
					!reflect.DeepEqual(gotCookies[i].Attrs, w.Cookies[i].Attrs) {
					t.Errorf("cookie %d: %+v, want %+v", i, gotCookies[i], w.Cookies[i])
				}
			}
			if w.ZipNames != nil {
				zr, err := zip.NewReader(bytes.NewReader(rec.Body.Bytes()), int64(len(rec.Body.Bytes())))
				if err != nil {
					t.Fatal(err)
				}
				names := make([]string, len(zr.File))
				for i, f := range zr.File {
					names[i] = f.Name
				}
				if !reflect.DeepEqual(names, w.ZipNames) {
					t.Errorf("zip names\n got  %v\n want %v", names, w.ZipNames)
				}
				var manifest map[string]any
				for _, f := range zr.File {
					if f.Name != "manifest.json" {
						continue
					}
					rc, err := f.Open()
					if err != nil {
						t.Fatal(err)
					}
					b, err := io.ReadAll(rc)
					_ = rc.Close()
					if err != nil {
						t.Fatal(err)
					}
					if err := json.Unmarshal(b, &manifest); err != nil {
						t.Fatal(err)
					}
					delete(manifest, "generated_at")
				}
				if !reflect.DeepEqual(manifest, w.Manifest) {
					gj, _ := json.Marshal(manifest)
					wj, _ := json.Marshal(w.Manifest)
					t.Errorf("manifest\n got  %s\n want %s", gj, wj)
				}
			}
			db := exportDump(t, ctx, pool)
			for name := range exportWatch {
				if !reflect.DeepEqual(db[name], w.DB[name]) {
					gj, _ := json.Marshal(db[name])
					wj, _ := json.Marshal(w.DB[name])
					t.Errorf("table %s:\n got  %s\n want %s", name, gj, wj)
				}
			}
		})
	}
}
