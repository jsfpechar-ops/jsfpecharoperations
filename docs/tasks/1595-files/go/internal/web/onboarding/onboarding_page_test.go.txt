package onboarding

// Tests of GET /onboarding (brief 1595). The golden cases are what
// App/scripts/go_onboarding_page_golden.py wrote from the real Python page.

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

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const onboardingPageSecret = "golden-secret-key-not-for-real-use"

type onboardingPageSeedTable struct {
	Table   string   `json:"table"`
	Columns []string `json:"columns"`
	Encrypt []string `json:"encrypt"`
	Rows    [][]any  `json:"rows"`
}

type onboardingPageGolden struct {
	PublicBase string                    `json:"public_base"`
	Seed       []onboardingPageSeedTable `json:"seed"`
	Cases      []struct {
		Name      string   `json:"name"`
		User      int64    `json:"user"`
		Workspace int64    `json:"workspace"`
		Lang      string   `json:"lang"`
		Env       *string  `json:"env"`
		Status    int      `json:"status"`
		Location  *string  `json:"location"`
		Lines     []string `json:"lines"`
	} `json:"cases"`
}

func loadOnboardingPageGolden(t *testing.T) onboardingPageGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/onboarding_page_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	var g onboardingPageGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 10 {
		t.Fatal("onboarding page golden file is too small")
	}
	return g
}

// onboardingPageSeed writes the golden SEED to PostgreSQL. Encrypted columns
// are encrypted with the Go data keys; "apartment_update" rows set a raw token.
func onboardingPageSeed(t *testing.T, pool *pgxpool.Pool, g onboardingPageGolden, getenv func(string) string) {
	t.Helper()
	ctx := context.Background()
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		t.Fatal(err)
	}
	value := func(v any) any {
		if n, ok := v.(json.Number); ok {
			i, err := n.Int64()
			if err != nil {
				t.Fatalf("seed number %v", n)
			}
			return i
		}
		return v
	}
	for _, table := range g.Seed {
		if table.Table == "apartment_update" {
			for _, row := range table.Rows {
				if _, err := pool.Exec(ctx, `UPDATE apartment SET uby_ws_password_enc = $1 WHERE id = $2`, value(row[1]), value(row[0])); err != nil {
					t.Fatal(err)
				}
			}
			continue
		}
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table.Table, strings.Join(table.Columns, ", "), strings.Join(marks, ", "))
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = value(v)
				for _, col := range table.Encrypt {
					if table.Columns[i] == col && v != nil {
						token, err := keys.EncryptString(v.(string))
						if err != nil {
							t.Fatal(err)
						}
						args[i] = token
					}
				}
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
}

// onboardingPageVisibleLines is visible_lines in
// App/scripts/go_onboarding_page_golden.py; keep the two in step.
var (
	onboardingPageDrop = []*regexp.Regexp{regexp.MustCompile(`(?s)<!--.*?-->`), regexp.MustCompile(`(?is)<script\b.*?</script>`),
		regexp.MustCompile(`(?is)<style\b.*?</style>`), regexp.MustCompile(`(?is)<svg\b.*?</svg>`)}
	onboardingPageToken = regexp.MustCompile(`<[^>]*>|[^<]+`)
	onboardingPageTag   = regexp.MustCompile(`^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)`)
	onboardingPageAttr  = regexp.MustCompile(`([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?`)
	onboardingPageSpace = regexp.MustCompile(`[ \t\n\r\f\v]+`)
	onboardingPageKept  = map[string]bool{"id": true, "href": true, "action": true, "method": true, "name": true, "value": true,
		"type": true, "selected": true, "checked": true, "required": true, "for": true, "aria-current": true,
		"class": true, "aria-label": true, "aria-controls": true, "data-copy": true, "target": true}
)

func onboardingPageVisibleLines(page string) []string {
	start := strings.Index(page, `<div class="ui-page"`)
	if start < 0 {
		return []string{}
	}
	page = page[start:]
	if end := strings.Index(page, `<div class="page-skeleton"`); end >= 0 {
		page = page[:end]
	}
	for _, re := range onboardingPageDrop {
		page = re.ReplaceAllString(page, "")
	}
	out := []string{}
	type attrVal struct {
		has   bool
		value string
	}
	for _, tok := range onboardingPageToken.FindAllString(page, -1) {
		if !strings.HasPrefix(tok, "<") {
			text := strings.Trim(onboardingPageSpace.ReplaceAllString(html.UnescapeString(tok), " "), " ")
			if text != "" {
				out = append(out, text)
			}
			continue
		}
		m := onboardingPageTag.FindStringSubmatchIndex(tok)
		if m == nil || tok[m[2]:m[3]] == "/" {
			continue
		}
		name := strings.ToLower(tok[m[4]:m[5]])
		attrs := map[string]attrVal{}
		for _, a := range onboardingPageAttr.FindAllStringSubmatch(tok[m[1]:], -1) {
			key := strings.ToLower(a[1])
			v := html.UnescapeString(a[2] + a[3] + a[4])
			if key == "class" {
				v = strings.Join(strings.Fields(v), " ")
			}
			attrs[key] = attrVal{strings.Contains(a[0], "="), v}
		}
		if attrs["name"].value == "_csrf" {
			attrs["value"] = attrVal{true, "*"}
		}
		keys := make([]string, 0, len(attrs))
		for k := range attrs {
			if onboardingPageKept[k] {
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

func TestOnboardingPageVisibleLines(t *testing.T) {
	page := `<p>x</p><div class="ui-page"><!-- c --><a class=" a  b " href="/b?a=1&amp;b=2"><span>Back</span></a>` +
		`<h1>T&#39;s  <b>bold</b></h1><input type="hidden" name="_csrf" value="tok"><input required name=q>` +
		`<svg><path d="M0"/></svg><select data-x="1"><option selected value="">All</option></select></div>` +
		`<div class="page-skeleton">skip</div>`
	want := []string{"<div class=ui-page>", "<a class=a b href=/b?a=1&b=2>", "Back", "T's", "bold",
		"<input name=_csrf type=hidden value=*>", "<input name=q required>", "<option selected value=>", "All"}
	if got := onboardingPageVisibleLines(page); strings.Join(got, "\n") != strings.Join(want, "\n") {
		t.Fatalf("got %q", got)
	}
}

// onboardingPageGetenv is the process environment of the tests.
func onboardingPageGetenv(publicBase string) func(string) string {
	env := map[string]string{"UBYHOST_SECRET_KEY": onboardingPageSecret, "UBYHOST_PUBLIC_BASE_URL": publicBase}
	return func(k string) string { return env[k] }
}

// onboardingPageGet sends GET /onboarding as user (0: signed out), previewing
// workspace when it is not 0, with the language cookie lang.
func onboardingPageGet(t *testing.T, h http.Handler, user, workspace int64, lang string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, "/onboarding", nil)
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	if user != 0 {
		payload := map[string]any{"uid": user, "sv": 1}
		if workspace != 0 {
			payload["as"] = workspace
			payload["ast"] = testNow.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(onboardingPageSecret, payload, testNow)})
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// TestOnboardingPageMatchesPython renders each golden case with the Go
// handler and compares the visible lines with the ones Python rendered. Go
// forms carry the _csrf field (Python's csrf.js adds it in the browser), so
// those lines are left out of the Go side before the compare.
func TestOnboardingPageMatchesPython(t *testing.T) {
	g := loadOnboardingPageGolden(t)
	pool := testPool(t)
	getenv := onboardingPageGetenv(g.PublicBase)
	onboardingPageSeed(t, pool, g, getenv)
	now := func() time.Time { return testNow }
	for _, c := range g.Cases {
		lookup := func(k string) (string, bool) {
			if k == "UBYHOST_UBYPORT_ENV" && c.Env != nil {
				return *c.Env, true
			}
			return "", false
		}
		rec := onboardingPageGet(t, OnboardingPageHandler(pool, getenv, lookup, now), c.User, c.Workspace, c.Lang)
		if rec.Code != c.Status {
			t.Errorf("%s: status %d, Python %d", c.Name, rec.Code, c.Status)
			continue
		}
		if c.Location != nil && rec.Header().Get("Location") != *c.Location {
			t.Errorf("%s: Location %q, Python %q", c.Name, rec.Header().Get("Location"), *c.Location)
		}
		if rec.Code != http.StatusOK {
			continue
		}
		var got []string
		for _, line := range onboardingPageVisibleLines(rec.Body.String()) {
			if line == "<input name=_csrf type=hidden value=*>" {
				continue
			}
			got = append(got, line)
		}
		body := rec.Body.String()
		area := body[strings.Index(body, `<section class="onboarding-welcome"`):]
		area = area[:strings.Index(area, `class="onboarding-foot"`)+strings.Index(area[strings.Index(area, `class="onboarding-foot"`):], `</div>`)]
		if forms := strings.Count(area, `<form method="post"`); forms == 0 || strings.Count(area, `name="_csrf"`) != forms {
			t.Errorf("%s: %d _csrf fields for %d forms", c.Name, strings.Count(area, `name="_csrf"`), forms)
		}
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
}

// TestOnboardingPageCreatesSlug: a finished single property without a
// current slug gets one (guest_slug.ensure through palette.LinkKey), and the
// next view shows the same one.
func TestOnboardingPageCreatesSlug(t *testing.T) {
	g := loadOnboardingPageGolden(t)
	pool := testPool(t)
	getenv := onboardingPageGetenv(g.PublicBase)
	onboardingPageSeed(t, pool, g, getenv)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `DELETE FROM apartment_slug WHERE apartment_id = 51`); err != nil {
		t.Fatal(err)
	}
	h := OnboardingPageHandler(pool, getenv, func(string) (string, bool) { return "", false }, func() time.Time { return testNow })
	first := onboardingPageGet(t, h, 5, 0, "en")
	var slug string
	if err := pool.QueryRow(ctx, `SELECT slug FROM apartment_slug WHERE apartment_id = 51 AND is_current = 1`).Scan(&slug); err != nil {
		t.Fatalf("no slug created: %v", err)
	}
	if !regexp.MustCompile(`^five-studio-[a-z0-9]{6}$`).MatchString(slug) {
		t.Fatalf("slug %q", slug)
	}
	for _, rec := range []*httptest.ResponseRecorder{first, onboardingPageGet(t, h, 5, 0, "en")} {
		body := rec.Body.String()
		if rec.Code != http.StatusOK || !strings.Contains(body, `>`+g.PublicBase+`/l/`+slug+`</code>`) || !strings.Contains(body, `href="/l/`+slug+`"`) {
			t.Fatalf("page does not show the slug %q: %d", slug, rec.Code)
		}
	}
	var n int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM apartment_slug WHERE apartment_id = 51`).Scan(&n); err != nil || n != 1 {
		t.Fatalf("%d slugs, want 1 (%v)", n, err)
	}
}

// TestOnboardingPageTemplateKeys: every key the page template asks for is in
// the page catalog in en, cs and vi (a missing key would show itself).
func TestOnboardingPageTemplateKeys(t *testing.T) {
	raw, err := os.ReadFile("onboardingpage/onboarding.tmpl")
	if err != nil {
		t.Fatal(err)
	}
	var keys []string
	for _, m := range regexp.MustCompile(`\(?t "([a-z_.]+)"`).FindAllStringSubmatch(string(raw), -1) {
		keys = append(keys, m[1])
	}
	for _, m := range regexp.MustCompile(`printf "onboarding\.%s\.([a-z_]+)" \$step\.ID`).FindAllStringSubmatch(string(raw), -1) {
		for _, id := range []string{"entity", "property", "calendars", "automation", "guest_link"} {
			if m[1] == "manual" && id != "calendars" {
				continue // only the calendars step has a manual_url
			}
			keys = append(keys, "onboarding."+id+"."+m[1])
		}
	}
	keys = append(keys, "apartment.form.passport_policy.off", "apartment.form.passport_policy.required")
	if len(keys) < 40 {
		t.Fatalf("only %d keys found", len(keys))
	}
	for _, lang := range []string{"en", "cs", "vi"} {
		for _, k := range keys {
			if _, ok := onboardingPageStrings[lang][k]; !ok {
				t.Errorf("%s: %s missing from onboardingpage/i18n.json", lang, k)
			}
		}
	}
}
