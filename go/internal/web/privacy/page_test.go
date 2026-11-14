package privacy

import (
	"context"
	"encoding/json"
	"fmt"
	"html"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// pageGolden is what App/scripts/privacy_requests_page_golden.py wrote from
// the real Python page.
type pageGolden struct {
	Versions map[string]string `json:"versions"`
	Seed     []struct {
		Table   string   `json:"table"`
		Columns []string `json:"columns"`
		Rows    [][]any  `json:"rows"`
	} `json:"seed"`
	Cases []struct {
		Name     string   `json:"name"`
		Account  int64    `json:"account"`
		Lang     string   `json:"lang"`
		Path     string   `json:"path"`
		Status   int      `json:"status"`
		Location string   `json:"location"`
		Lines    []string `json:"lines"`
	} `json:"cases"`
}

func loadPageGolden(t *testing.T) pageGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/privacy_requests_page_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g pageGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 6 {
		t.Fatal("page golden file is too small")
	}
	return g
}

// visibleLines is visible_lines in App/scripts/privacy_requests_page_golden.py;
// keep the two in step.
var (
	dropRes = []*regexp.Regexp{regexp.MustCompile(`(?s)<!--.*?-->`), regexp.MustCompile(`(?is)<script\b.*?</script>`),
		regexp.MustCompile(`(?is)<style\b.*?</style>`), regexp.MustCompile(`(?is)<svg\b.*?</svg>`)}
	tokenRe = regexp.MustCompile(`<[^>]*>|[^<]+`)
	tagRe   = regexp.MustCompile(`^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)`)
	attrRe  = regexp.MustCompile(`([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?`)
	spaceRe = regexp.MustCompile(`[ \t\n\r\f\v]+`)
	kept    = map[string]bool{"id": true, "href": true, "action": true, "method": true, "name": true, "value": true,
		"type": true, "selected": true, "checked": true, "required": true, "for": true, "aria-current": true,
		"aria-label": true, "open": true, "inputmode": true, "class": true}
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
	for _, tok := range tokenRe.FindAllString(page, -1) {
		if !strings.HasPrefix(tok, "<") {
			text := strings.Trim(spaceRe.ReplaceAllString(html.UnescapeString(tok), " "), " ")
			if text != "" {
				out = append(out, text)
			}
			continue
		}
		m := tagRe.FindStringSubmatchIndex(tok)
		if m == nil || tok[m[2]:m[3]] == "/" {
			continue
		}
		name := strings.ToLower(tok[m[4]:m[5]])
		attrs := map[string]attrVal{}
		for _, a := range attrRe.FindAllStringSubmatch(tok[m[1]:], -1) {
			key := strings.ToLower(a[1])
			value := html.UnescapeString(a[2] + a[3] + a[4])
			if key == "class" {
				value = strings.Join(strings.Fields(value), " ")
			}
			attrs[key] = attrVal{strings.Contains(a[0], "="), value}
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
	page := `<p>x</p><div class="ui-page"><!-- c --><details class=" card  x" open><summary>S</summary>` +
		`<h1>T&#39;s  <b>bold</b></h1><input type="hidden" name="_csrf" value="tok"><input required name=q>` +
		`<svg><path d="M0"/></svg><select data-x="1"><option selected value="">All</option></select></details></div>` +
		`<div class="page-skeleton">skip</div>`
	want := []string{"<div class=ui-page>", "<details class=card x open>", "S", "T's", "bold",
		"<input name=_csrf type=hidden value=*>", "<input name=q required>", "<option selected value=>", "All"}
	if got := visibleLines(page); strings.Join(got, "\n") != strings.Join(want, "\n") {
		t.Fatalf("got %q", got)
	}
}

func TestDateCZ(t *testing.T) {
	for in, want := range map[string]string{
		"2026-02-28": "28.02.2026", "2026-10-02 08:00": "02.10.2026",
		"2026-03-31T23:15:00+02:00": "31.03.2026", "garbage": "garbage", "": "", "2026-13-01": "2026-13-01",
	} {
		if got := dateCZ(in); got != want {
			t.Errorf("dateCZ(%q) = %q, want %q", in, got, want)
		}
	}
}

// pageEnv is testEnv with the legal versions the page golden signed in with.
func pageEnv(versions map[string]string) func(string) string {
	return func(k string) string {
		switch k {
		case "UBYHOST_TERMS_VERSION":
			return versions["terms"]
		case "UBYHOST_PRIVACY_VERSION":
			return versions["privacy"]
		case "UBYHOST_DPA_VERSION":
			return versions["dpa"]
		}
		return testEnv(k)
	}
}

func getPage(mux *http.ServeMux, path, lang string, account int64, at time.Time) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, path, nil)
	if account != 0 {
		payload := map[string]any{"uid": account, "sv": int64(1), "iat": at.Unix()}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, at)})
	}
	if lang != "" {
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

// TestListPageMatchesPython seeds PostgreSQL from the page golden, renders
// each case with ListHandler and compares the visible lines with Python's.
func TestListPageMatchesPython(t *testing.T) {
	g := loadPageGolden(t)
	pool := testPool(t)
	ctx := context.Background()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table.Table,
			strings.Join(table.Columns, ", "), strings.Join(marks, ", "))
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = seedValue(v)
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
	at := time.Date(2026, 11, 13, 9, 30, 0, 0, time.UTC)
	mux := http.NewServeMux()
	mux.Handle("GET /privacy-requests", ListHandler(pool, pageEnv(g.Versions), func() time.Time { return at }))
	for _, c := range g.Cases {
		rec := getPage(mux, c.Path, c.Lang, c.Account, at)
		if rec.Code != c.Status || rec.Header().Get("Location") != c.Location {
			t.Errorf("%s: %d %q, Python %d %q", c.Name, rec.Code, rec.Header().Get("Location"), c.Status, c.Location)
			continue
		}
		got := visibleLines(rec.Body.String())
		for i := 0; i < len(got) || i < len(c.Lines); i++ {
			var gl, wl string
			if i < len(got) {
				gl = got[i]
			}
			if i < len(c.Lines) {
				wl = c.Lines[i]
			}
			if gl != wl {
				t.Errorf("%s: line %d is %q, Python %q", c.Name, i, gl, wl)
				break
			}
		}
	}
	// Signed out: require_login sends the visitor to the login page, before
	// any query of the register.
	rec := getPage(mux, "/privacy-requests", "en", 0, at)
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/login") {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if strings.Contains(rec.Body.String(), "privacy-requests/61") {
		t.Error("signed out: the page leaked a request")
	}
}
