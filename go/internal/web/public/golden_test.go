package public

import (
	"encoding/json"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"text/template/parse"
)

// goldenCase is one entry of testdata/cases.json (App/scripts/public_legal_golden.py).
type goldenCase struct {
	Name     string            `json:"name"`
	Path     string            `json:"path"`
	Query    string            `json:"query"`
	Cookies  map[string]string `json:"cookies"`
	Env      map[string]string `json:"env"`
	Expected struct {
		Status      int            `json:"status"`
		ContentType string         `json:"content_type"`
		CacheCtl    string         `json:"cache_control"`
		CSP         string         `json:"csp"`
		SetCookies  []goldenCookie `json:"set_cookies"`
	} `json:"expected"`
}

type goldenCookie struct {
	Name     string `json:"name"`
	Value    string `json:"value"`
	Path     string `json:"path"`
	MaxAge   string `json:"max_age"`
	SameSite string `json:"samesite"`
	Secure   bool   `json:"secure"`
	HTTPOnly bool   `json:"httponly"`
}

var space = regexp.MustCompile(`[ \t\n\r\f\v]+`)

// normalize is public_legal_golden.normalize: ASCII whitespace runs become
// one space, "> <" becomes "><", ends trimmed.
func normalize(s string) string {
	return strings.TrimSpace(strings.ReplaceAll(space.ReplaceAllString(s, " "), "> <", "><"))
}

// defaultHeaders stands in for main.go's wrap(), which sets these before the handler.
func serve(t *testing.T, c goldenCase) *httptest.ResponseRecorder {
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
	getenv := func(k string) string { return c.Env[k] }
	Handler(c.Path, Deps{Getenv: getenv})(rec, req)
	return rec
}

// wrapCSP is the Content-Security-Policy main.go's hardenHeaders sets.
const wrapCSP = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self' https://challenges.cloudflare.com"

func TestGoldenPages(t *testing.T) {
	raw, err := os.ReadFile("testdata/cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []goldenCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) < 30 {
		t.Fatalf("only %d golden cases", len(cases))
	}
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			rec := serve(t, c)
			want, err := os.ReadFile(filepath.Join("testdata", c.Name+".html"))
			if err != nil {
				t.Fatal(err)
			}
			got := normalize(rec.Body.String()) + "\n"
			if got != string(want) {
				t.Errorf("html differs at byte %d:\n got: %s\nwant: %s", firstDiff(got, string(want)),
					around(got, firstDiff(got, string(want))), around(string(want), firstDiff(got, string(want))))
			}
			e := c.Expected
			if rec.Code != e.Status {
				t.Errorf("status %d, want %d", rec.Code, e.Status)
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
			if len(cookies) == 0 && len(e.SetCookies) == 0 {
				return
			}
			if string(gotC) != string(wantC) {
				t.Errorf("set-cookie %s, want %s", gotC, wantC)
			}
		})
	}
}

func itoa(n int) string {
	b, _ := json.Marshal(n)
	return string(b)
}

func firstDiff(a, b string) int {
	for i := 0; i < len(a) && i < len(b); i++ {
		if a[i] != b[i] {
			return i
		}
	}
	return min(len(a), len(b))
}

func around(s string, i int) string {
	lo, hi := max(0, i-80), min(len(s), i+80)
	return s[lo:hi]
}

func TestHeadHasNoBody(t *testing.T) {
	req := httptest.NewRequest(http.MethodHead, "/legal", nil)
	rec := httptest.NewRecorder()
	Handler("/legal", Deps{Getenv: func(string) string { return "" }})(rec, req)
	if rec.Code != http.StatusOK || rec.Body.Len() != 0 {
		t.Fatalf("HEAD: %d with %d bytes", rec.Code, rec.Body.Len())
	}
}

// allowedPrints are the only things a template may print: the escaping
// methods, and fields that hold no outside text (Lang is "en" or "cs", Path
// is one of Paths, WrapClass is "narrow", the PH*JS fields are tojson output).
var allowedPrints = map[string]bool{
	"T": true, "TL": true, "E": true, "L": true, "Effective": true, "URL": true, "Canonical": true,
	"Lang": true, "Path": true, "WrapClass": true, "PHKeyJS": true, "PHHostJS": true, "PHAssetsJS": true,
}

func TestEveryActionEscapes(t *testing.T) {
	files, _ := fs.Glob(templateFS, "templates/*.tmpl")
	for _, file := range files {
		src, _ := fs.ReadFile(templateFS, file)
		trees, err := parse.Parse(file, string(src), "{{", "}}", map[string]any{"printf": true, "eq": true, "ne": true, "and": true})
		if err != nil {
			t.Fatal(err)
		}
		for _, tree := range trees {
			walk(t, file, tree.Root)
		}
	}
}

func walk(t *testing.T, file string, n parse.Node) {
	switch n := n.(type) {
	case *parse.ListNode:
		if n == nil {
			return
		}
		for _, c := range n.Nodes {
			walk(t, file, c)
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
		if !allowedPrints[name] {
			t.Errorf("%s: %s prints without escaping", file, n)
		}
	case *parse.IfNode:
		walk(t, file, n.List)
		walk(t, file, n.ElseList)
	case *parse.RangeNode:
		walk(t, file, n.List)
		walk(t, file, n.ElseList)
	case *parse.WithNode:
		walk(t, file, n.List)
		walk(t, file, n.ElseList)
	}
}
