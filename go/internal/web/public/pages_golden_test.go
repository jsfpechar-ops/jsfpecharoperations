package public

import (
	"encoding/json"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"text/template/parse"
)

func pagesMux(d Deps) *http.ServeMux {
	mux := http.NewServeMux()
	mux.Handle("GET /jak-to-funguje", ProductHandler(d))
	mux.Handle(GuidePattern, GuideHandler(d))
	if PricingHandler != nil {
		mux.Handle("GET /cenik", PricingHandler(d))
	}
	return mux
}

func servePage(t *testing.T, c goldenCase, signedIn bool) *httptest.ResponseRecorder {
	t.Helper()
	url := c.Path
	if c.Query != "" {
		url += "?" + c.Query
	}
	req := httptest.NewRequest(http.MethodGet, url, nil)
	for k, v := range c.Cookies {
		req.AddCookie(&http.Cookie{Name: k, Value: v})
	}
	rec := httptest.NewRecorder()
	rec.Header().Set("Cache-Control", "no-store, private")
	rec.Header().Set("Content-Security-Policy", wrapCSP)
	d := Deps{Getenv: func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return "public-legal-golden-secret-not-real-0123" // the golden script's key
		}
		return c.Env[k]
	}}
	if signedIn {
		d.SignedIn = func(*http.Request) bool { return true }
	}
	pagesMux(d).ServeHTTP(rec, req)
	return rec
}

func loadPageCases(t *testing.T) []goldenCase {
	t.Helper()
	raw, err := os.ReadFile("testdata/pages/cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []goldenCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	return cases
}

// TestPagesGolden compares every product, pricing and guide case with the
// FastAPI page: normalized HTML, status, headers and the language cookie.
func TestPagesGolden(t *testing.T) {
	cases := loadPageCases(t)
	if len(cases) < 20 {
		t.Fatalf("only %d golden cases", len(cases))
	}
	for _, c := range cases {
		if strings.HasPrefix(c.Name, "pricing") && PricingHandler == nil {
			continue
		}
		t.Run(c.Name, func(t *testing.T) {
			rec := servePage(t, c, false)
			e := c.Expected
			if rec.Code != e.Status {
				t.Fatalf("status %d, want %d", rec.Code, e.Status)
			}
			want, err := os.ReadFile(filepath.Join("testdata/pages", c.Name+".html"))
			if err != nil {
				t.Fatal(err)
			}
			got := normalize(rec.Body.String()) + "\n"
			if e.Status != 200 {
				if strings.TrimSpace(got) != strings.TrimSpace(string(want)) {
					t.Errorf("body %q, want %q", got, want)
				}
			} else if got != string(want) {
				i := firstDiff(got, string(want))
				t.Errorf("html differs at byte %d:\n got: %s\nwant: %s", i, around(got, i), around(string(want), i))
			}
			h := rec.Header()
			if h.Get("Content-Type") != e.ContentType || h.Get("Cache-Control") != e.CacheCtl || h.Get("Content-Security-Policy") != e.CSP {
				t.Errorf("headers %q %q %q, want %q %q %q", h.Get("Content-Type"), h.Get("Cache-Control"),
					h.Get("Content-Security-Policy"), e.ContentType, e.CacheCtl, e.CSP)
			}
			var cookies []goldenCookie
			for _, line := range h.Values("Set-Cookie") {
				ck, err := http.ParseSetCookie(line)
				if err != nil {
					t.Fatal(err)
				}
				ss := map[http.SameSite]string{http.SameSiteLaxMode: "lax", http.SameSiteStrictMode: "strict"}[ck.SameSite]
				cookies = append(cookies, goldenCookie{ck.Name, ck.Value, ck.Path, itoa(ck.MaxAge), ss, ck.Secure, ck.HttpOnly})
			}
			gotC, _ := json.Marshal(cookies)
			wantC, _ := json.Marshal(e.SetCookies)
			if len(cookies) > 0 || len(e.SetCookies) > 0 {
				if string(gotC) != string(wantC) {
					t.Errorf("set-cookie %s, want %s", gotC, wantC)
				}
			}
		})
	}
}

// TestPagesPostHogOnlyWhenConfigured: with no POSTHOG_PROJECT_API_KEY no page
// carries a script from outside, and the strict CSP stays; with a key the tag
// and its CSP appear (the pages are on analytics.PUBLIC_ANALYTICS_TEMPLATES).
func TestPagesPostHogOnlyWhenConfigured(t *testing.T) {
	for _, c := range loadPageCases(t) {
		if c.Expected.Status != 200 || (strings.HasPrefix(c.Name, "pricing") && PricingHandler == nil) {
			continue
		}
		rec := servePage(t, c, false)
		body, withKey := rec.Body.String(), c.Env["POSTHOG_PROJECT_API_KEY"] != ""
		if has := strings.Contains(body, "posthog"); has != withKey {
			t.Errorf("%s: posthog in page = %v, key set = %v", c.Name, has, withKey)
		}
		if strings.Contains(rec.Header().Get("Content-Security-Policy"), "posthog") != withKey {
			t.Errorf("%s: CSP and key disagree", c.Name)
		}
		if strings.Count(body, "<script src=") > 1 || (!withKey && strings.Contains(body, "https://eu-assets")) {
			t.Errorf("%s: unexpected external script", c.Name)
		}
	}
}

// TestGuideVietnameseServesEnglish: Python raises KeyError (HTTP 500) for
// ?lang=vi because GUIDE_TRANSLATIONS has no "vi"; Go serves the English guide.
func TestGuideVietnameseServesEnglish(t *testing.T) {
	c := goldenCase{Path: "/pruvodce/hlaseni-cizincu-ubyport", Query: "lang=vi", Env: map[string]string{"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example"}}
	rec := servePage(t, c, false)
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), `<html lang="en">`) ||
		!strings.Contains(rec.Body.String(), `href="https://ubyhost.example/pruvodce/hlaseni-cizincu-ubyport?lang=vi"`) {
		t.Fatalf("status %d, body start %.200s", rec.Code, rec.Body.String())
	}
}

// TestSignedInHostKeepsPublicRouteLanguage: a signed-in host with no language
// choice gets English chrome (templating.render) but the Czech guide text,
// because legal.public_guide resolves its own language with the public default.
func TestSignedInHostKeepsPublicRouteLanguage(t *testing.T) {
	c := goldenCase{Path: "/pruvodce/hlaseni-cizincu-ubyport", Env: map[string]string{"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example"}}
	body := servePage(t, c, true).Body.String()
	if !strings.Contains(body, `<html lang="en">`) || !strings.Contains(body, "Hlášení cizinců přes UbyPort") {
		t.Fatalf("signed-in page: %.300s", body)
	}
}

func TestPagesHeadHasNoBody(t *testing.T) {
	for _, path := range []string{"/jak-to-funguje", "/pruvodce/hlaseni-cizincu-ubyport"} {
		rec := httptest.NewRecorder()
		pagesMux(Deps{Getenv: func(string) string { return "" }}).ServeHTTP(rec, httptest.NewRequest(http.MethodHead, path, nil))
		if rec.Code != http.StatusOK || rec.Body.Len() != 0 {
			t.Fatalf("HEAD %s: %d with %d bytes", path, rec.Code, rec.Body.Len())
		}
	}
}

// TestPyJSON pins |tojson on values Python printed (sorted keys, ", " and ": ",
// \u escapes for non-ASCII and < > & ').
func TestPyJSON(t *testing.T) {
	got := pyJSON(map[string]any{"b": []any{1, "\u00e1", "<a href='x'>&"}, "a": map[string]any{"z": float64(470), "y": "\U0001D11E\n\"\\"}})
	bs := "\\"
	want := `{"a": {"y": "` + bs + `ud834` + bs + `udd1e` + bs + `n` + bs + `"` + bs + bs + `", "z": 470}, "b": [1, "` + bs + `u00e1", "` +
		bs + `u003ca href=` + bs + `u0027x` + bs + `u0027` + bs + `u003e` + bs + `u0026"]}`
	if got != want {
		t.Fatalf("pyJSON:\n got %s\nwant %s", got, want)
	}
}

// pagePrints are the only things a marketing template may print.
var pagePrints = map[string]bool{
	"T": true, "TP": true, "E": true, "Icon": true, "Canonical": true, "PublicBase": true, "URL": true,
	"LangIf": true, "OGLocale": true, "OfficialLink": true, "FAQJSON": true, "ArticleJSON": true,
	"Lang": true, "SwitchPath": true, "Code": true, "Href": true, "PHKeyJS": true, "PHHostJS": true, "PHAssetsJS": true,
	"CTA": true, "RatesJSON": true, "WebPageJSON": true, "PricingFAQJSON": true,
	"StdMonth": true, "MaxMonth": true, "StdYear": true, "MaxYear": true, "TTLockMonth": true, "Band": true, "Tick": true,
}

func TestPagesEveryActionEscapes(t *testing.T) {
	files, _ := fs.Glob(pagesFS, "templates/pages/*.tmpl")
	if len(files) < 6 {
		t.Fatalf("only %d page templates", len(files))
	}
	for _, file := range files {
		src, _ := fs.ReadFile(pagesFS, file)
		trees, err := parse.Parse(file, string(src), "{{", "}}", map[string]any{"printf": true, "eq": true, "ne": true, "and": true, "index": true})
		if err != nil {
			t.Fatal(err)
		}
		for _, tree := range trees {
			walkPages(t, file, tree.Root)
		}
	}
}

func walkPages(t *testing.T, file string, n parse.Node) {
	switch n := n.(type) {
	case *parse.ListNode:
		if n == nil {
			return
		}
		for _, c := range n.Nodes {
			walkPages(t, file, c)
		}
	case *parse.ActionNode:
		if len(n.Pipe.Decl) > 0 {
			return
		}
		cmd := n.Pipe.Cmds[len(n.Pipe.Cmds)-1]
		name := ""
		switch a := cmd.Args[0].(type) {
		case *parse.FieldNode:
			name = a.Ident[len(a.Ident)-1]
		case *parse.VariableNode:
			if len(a.Ident) > 1 {
				name = a.Ident[len(a.Ident)-1]
			}
		}
		if !pagePrints[name] {
			t.Errorf("%s: %s prints without escaping", file, n)
		}
	case *parse.IfNode:
		walkPages(t, file, n.List)
		walkPages(t, file, n.ElseList)
	case *parse.RangeNode:
		walkPages(t, file, n.List)
		walkPages(t, file, n.ElseList)
	case *parse.WithNode:
		walkPages(t, file, n.List)
		walkPages(t, file, n.ElseList)
	}
}
