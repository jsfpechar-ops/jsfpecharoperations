package customers

import (
	"encoding/json"
	"html"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strings"
	"testing"
	"time"
)

// pagesGolden is what App/scripts/go_customers_pages_golden.py wrote from the
// real Python pages.
type pagesGolden struct {
	UTCNow struct {
		At    string `json:"at"`
		Stamp string `json:"stamp"`
	} `json:"utcnow"`
	Cases []struct {
		Name    string   `json:"name"`
		Lang    string   `json:"lang"`
		Billing bool     `json:"billing"`
		Path    string   `json:"path"`
		Status  int      `json:"status"`
		Lines   []string `json:"lines"`
	} `json:"cases"`
}

func loadPagesGolden(t *testing.T) pagesGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/customers_pages_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g pagesGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 9 {
		t.Fatal("pages golden file is too small")
	}
	return g
}

// visibleLines is visible_lines in App/scripts/go_customers_pages_golden.py;
// keep the two in step.
var (
	dropRes = []*regexp.Regexp{regexp.MustCompile(`(?s)<!--.*?-->`), regexp.MustCompile(`(?is)<script\b.*?</script>`),
		regexp.MustCompile(`(?is)<style\b.*?</style>`), regexp.MustCompile(`(?is)<svg\b.*?</svg>`)}
	tokenRe = regexp.MustCompile(`<[^>]*>|[^<]+`)
	tagRe   = regexp.MustCompile(`^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)`)
	attrRe  = regexp.MustCompile(`([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?`)
	spaceRe = regexp.MustCompile(`[ \t\n\r\f\v]+`)
	kept    = map[string]bool{"id": true, "href": true, "action": true, "method": true, "name": true, "value": true,
		"type": true, "selected": true, "checked": true, "required": true, "for": true, "aria-current": true}
)

type attrVal struct {
	has   bool
	value string
}

func visibleLines(page string) []string {
	start := strings.Index(page, `<div class="ui-page"`)
	if start < 0 {
		return []string{}
	}
	page = page[start:]
	if end := strings.Index(page, `<div class="page-skeleton"`); end >= 0 {
		page = page[:end]
	}
	for _, re := range dropRes {
		page = re.ReplaceAllString(page, "")
	}
	out := []string{}
	skip := false
	for _, tok := range tokenRe.FindAllString(page, -1) {
		if !strings.HasPrefix(tok, "<") {
			text := strings.Trim(spaceRe.ReplaceAllString(html.UnescapeString(tok), " "), " ")
			if text != "" && !skip {
				out = append(out, text)
			}
			continue
		}
		m := tagRe.FindStringSubmatchIndex(tok)
		if m == nil {
			continue
		}
		name := strings.ToLower(tok[m[4]:m[5]])
		if tok[m[2]:m[3]] == "/" {
			if name == "a" {
				skip = false
			}
			continue
		}
		attrs := map[string]attrVal{}
		for _, a := range attrRe.FindAllStringSubmatch(tok[m[1]:], -1) {
			attrs[strings.ToLower(a[1])] = attrVal{strings.Contains(a[0], "="), html.UnescapeString(a[2] + a[3] + a[4])}
		}
		for _, c := range strings.Fields(attrs["class"].value) {
			if c == "ui-ph-back" {
				skip = true
			}
		}
		if attrs["name"].value == "_csrf" {
			attrs["value"] = attrVal{true, "*"}
		}
		keys := make([]string, 0, len(attrs))
		for k := range attrs {
			if kept[k] {
				keys = append(keys, k)
			}
		}
		sort.Strings(keys)
		parts := make([]string, len(keys))
		for i, k := range keys {
			parts[i] = k
			if attrs[k].has {
				parts[i] += "=" + attrs[k].value
			}
		}
		if len(parts) > 0 {
			out = append(out, "<"+name+" "+strings.Join(parts, " ")+">")
		}
	}
	return out
}

func TestVisibleLines(t *testing.T) {
	page := `<p>x</p><div class="ui-page"><!-- c --><a class="ui-ph-back x" href="/b?a=1&amp;b=2"><span>Back</span></a>` +
		`<h1>T&#39;s  <b>bold</b></h1><input type="hidden" name="_csrf" value="tok"><input required name=q>` +
		`<svg><path d="M0"/></svg><select data-x="1"><option selected value="">All</option></select></div>` +
		`<div class="page-skeleton">skip</div>`
	want := []string{"<a href=/b?a=1&b=2>", "T's", "bold", "<input name=_csrf type=hidden value=*>",
		"<input name=q required>", "<option selected value=>", "All"}
	if got := visibleLines(page); strings.Join(got, "\n") != strings.Join(want, "\n") {
		t.Fatalf("got %q", got)
	}
}

// pagesMux routes the GET pages the way register_web_customers.go does.
func pagesMux(t *testing.T, g goldenFile, billing bool) *http.ServeMux {
	t.Helper()
	pool := dbPool(t)
	seed(t, pool, g)
	base := testGetenv(g.Versions)
	getenv := func(k string) string {
		if k == "UBYHOST_BILLING_ENABLED" {
			if billing {
				return "1"
			}
			return "0"
		}
		return base(k)
	}
	now := func() time.Time { return testNow }
	mux := http.NewServeMux()
	mux.Handle("GET /admin/customers", ListHandler(pool, getenv, now))
	return mux
}

// TestPagesMatchPython renders each golden case with the Go handler and
// compares the visible lines with the ones Python rendered.
func TestPagesMatchPython(t *testing.T) {
	g := loadGolden(t)
	pg := loadPagesGolden(t)
	muxes := map[bool]*http.ServeMux{true: pagesMux(t, g, true), false: pagesMux(t, g, false)}
	for _, c := range pg.Cases {
		rec := serve(t, muxes[c.Billing], call{method: "GET", path: c.Path, lang: c.Lang,
			payload: map[string]any{"uid": 1, "sv": 1}})
		if rec.Code != c.Status {
			t.Errorf("%s: status %d, Python %d", c.Name, rec.Code, c.Status)
			continue
		}
		got := visibleLines(rec.Body.String())
		for i := 0; i < len(got) || i < len(c.Lines); i++ {
			var g, w string
			if i < len(got) {
				g = got[i]
			}
			if i < len(c.Lines) {
				w = c.Lines[i]
			}
			if g != w {
				t.Errorf("%s: line %d is %q, Python %q", c.Name, i, g, w)
				break
			}
		}
	}
}

// TestPagesNeedAdmin: a signed-out visitor goes to the login page and a host
// gets the 403 text, as _require_admin answers.
func TestPagesNeedAdmin(t *testing.T) {
	g := loadGolden(t)
	mux := pagesMux(t, g, true)
	rec := serve(t, mux, call{method: "GET", path: "/admin/customers", lang: "en"})
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/login") {
		t.Fatalf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	rec = serve(t, mux, call{method: "GET", path: "/admin/customers", lang: "en",
		payload: map[string]any{"uid": 7, "sv": 1}})
	if rec.Code != http.StatusForbidden || rec.Body.String() != "Administrators only." {
		t.Fatalf("host: %d %q", rec.Code, rec.Body.String())
	}
}

// TestStampMatchesUTCNow: the audit "at" value has db.utcnow's format.
func TestStampMatchesUTCNow(t *testing.T) {
	pg := loadPagesGolden(t)
	at, err := time.Parse(time.RFC3339Nano, pg.UTCNow.At)
	if err != nil {
		t.Fatal(err)
	}
	if got := stamp(at.In(prague)); got != pg.UTCNow.Stamp {
		t.Fatalf("stamp %q, db.utcnow %q", got, pg.UTCNow.Stamp)
	}
}
