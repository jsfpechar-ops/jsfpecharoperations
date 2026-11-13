package properties

import (
	"encoding/json"
	"html"
	"net/http"
	"net/http/httptest"
	"reflect"
	"regexp"
	"sort"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// The cases and golden written by App/tests/test_go_properties_pages.py.
type pageCase struct {
	Name string            `json:"name"`
	Path string            `json:"path"`
	User int64             `json:"user"`
	As   int64             `json:"as"`
	Lang string            `json:"lang"`
	Env  map[string]string `json:"env"`
}

type pageGolden struct {
	Name     string   `json:"name"`
	Status   int      `json:"status"`
	Location string   `json:"location"`
	Title    string   `json:"title"`
	Items    []string `json:"items"`
}

// extractItems mirrors extract_items in the Python test: the div.ui-page
// element as tags (attributes sorted), end tags and text runs, whitespace
// squashed and entities unescaped.
var (
	htmlTokenRE = regexp.MustCompile(`(?s)<!--.*?-->|<[^>]*>|[^<]+`)
	attrRE      = regexp.MustCompile(`([^\s=/>"']+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']+)))?`)
	spaceRE     = regexp.MustCompile(`[ \t\n\r\f]+`)
	titleRE     = regexp.MustCompile(`(?s)<title>(.*?)</title>`)
)

func squash(s string) string {
	return strings.Trim(spaceRE.ReplaceAllString(html.UnescapeString(s), " "), " ")
}

func extractItems(body string) []string {
	start := strings.Index(body, `<div class="ui-page"`)
	if start < 0 {
		return []string{}
	}
	items := []string{}
	depth := 0
	for _, tok := range htmlTokenRE.FindAllString(body[start:], -1) {
		switch {
		case strings.HasPrefix(tok, "<!--"):
			continue
		case !strings.HasPrefix(tok, "<"):
			if text := squash(tok); text != "" {
				items = append(items, text)
			}
			continue
		case strings.HasPrefix(tok, "</"):
			name := strings.ToLower(strings.TrimSpace(tok[2 : len(tok)-1]))
			items = append(items, "</"+name+">")
			if name == "div" {
				depth--
				if depth == 0 {
					return items
				}
			}
			continue
		}
		inner := strings.TrimSpace(strings.TrimRight(tok[1:len(tok)-1], "/"))
		name, rest, _ := strings.Cut(inner, " ")
		name = strings.ToLower(name)
		attrs := map[string]*string{}
		for _, m := range attrRE.FindAllStringSubmatchIndex(rest, -1) {
			key := strings.ToLower(rest[m[2]:m[3]])
			var val *string
			for g := 2; g <= 4; g++ {
				if m[2*g] >= 0 {
					v := squash(rest[m[2*g]:m[2*g+1]])
					val = &v
					break
				}
			}
			attrs[key] = val
		}
		if name == "input" && attrs["name"] != nil && *attrs["name"] == "_csrf" {
			v := "<csrf>"
			attrs["value"] = &v
		}
		keys := make([]string, 0, len(attrs))
		for k := range attrs {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		parts := []string{name}
		for _, k := range keys {
			if attrs[k] == nil {
				parts = append(parts, k)
			} else {
				parts = append(parts, k+"="+*attrs[k])
			}
		}
		items = append(items, "<"+strings.Join(parts, " ")+">")
		if name == "div" {
			depth++
		}
	}
	return items
}

func TestExtractItemsScope(t *testing.T) {
	page := `<p>out</p><div class="ui-page" data-x><div>a &amp; b</div><input name="_csrf" value="t" hidden></div><p>after</p>`
	want := []string{"<div class=ui-page data-x>", "<div>", "a & b", "</div>", "<input hidden name=_csrf value=<csrf>>", "</div>"}
	if got := extractItems(page); !reflect.DeepEqual(got, want) {
		t.Errorf("got %q", got)
	}
}

func TestPagesMatchPython(t *testing.T) {
	pool := testPool(t)
	var c casesFile
	readJSON(t, "pages_cases.json", &c)
	var raw struct {
		Cases []pageCase `json:"cases"`
	}
	readJSON(t, "pages_cases.json", &raw)
	var golden []pageGolden
	readJSON(t, "pages_golden.json", &golden)
	if len(golden) != len(raw.Cases) || len(golden) < 8 {
		t.Fatalf("golden has %d cases, cases file %d", len(golden), len(raw.Cases))
	}
	seedWorld(t, pool, &c)
	for i, tc := range raw.Cases {
		env := func(k string) string {
			if v, ok := tc.Env[k]; ok {
				return v
			}
			return testEnv(k)
		}
		lookup := func(k string) (string, bool) {
			if v, ok := tc.Env[k]; ok {
				return v, true
			}
			v := testEnv(k)
			return v, v != ""
		}
		mux := http.NewServeMux()
		RegisterPages(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, env, lookup, testClock)
		req := httptest.NewRequest(http.MethodGet, tc.Path, nil)
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: tc.Lang})
		if tc.User != 0 {
			payload := map[string]any{"uid": tc.User, "sv": int64(1), "iat": testNow.Unix()}
			if tc.As != 0 {
				payload["as"] = tc.As
				payload["ast"] = testNow.Unix()
			}
			req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		body := ""
		if rec.Code == http.StatusOK {
			body = rec.Body.String()
		}
		got := pageGolden{Name: tc.Name, Status: rec.Code, Location: rec.Header().Get("Location"), Items: extractItems(body)}
		if m := titleRE.FindStringSubmatch(body); m != nil {
			got.Title = squash(m[1])
		}
		want := golden[i]
		if want.Items == nil {
			want.Items = []string{}
		}
		if got.Name != want.Name || got.Status != want.Status || got.Location != want.Location || got.Title != want.Title {
			g, _ := json.Marshal(pageGolden{got.Name, got.Status, got.Location, got.Title, nil})
			w, _ := json.Marshal(pageGolden{want.Name, want.Status, want.Location, want.Title, nil})
			t.Errorf("case %d differs\n got: %s\nwant: %s", i, g, w)
			continue
		}
		if !reflect.DeepEqual(got.Items, want.Items) {
			n := 0
			for n < len(got.Items) && n < len(want.Items) && got.Items[n] == want.Items[n] {
				n++
			}
			lo := max(0, n-3)
			t.Errorf("case %s: items differ at %d (go %d, py %d)\n go: %q\n py: %q", tc.Name, n, len(got.Items), len(want.Items),
				got.Items[lo:min(len(got.Items), n+4)], want.Items[lo:min(len(want.Items), n+4)])
		}
	}
}

func TestPagesRegisterDoesNotTouchThePool(t *testing.T) {
	mux := http.NewServeMux()
	RegisterPages(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, nil, testEnv, func(string) (string, bool) { return "", false }, testClock)
	req := httptest.NewRequest(http.MethodPost, "/guide", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("POST /guide: code %d, want 405", rec.Code)
	}
}
