package opspage

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"html"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session/admingate"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

// Parity: routes/admin_accounts.py operations_admin (929-950), admin_ops.py,
// incidents.py, havel.admin_overview and the template admin_operations.html.
// testdata/admin_operations_golden.json is what App/scripts/admin_operations_golden.py
// rendered with the real Python page from the same seed.

const testSecret = "golden-secret-key-not-for-real-use"

type golden struct {
	Now      string            `json:"now"`
	Versions map[string]string `json:"versions"`
	Seed     []struct {
		Table string           `json:"table"`
		Rows  []map[string]any `json:"rows"`
	} `json:"seed"`
	Cases []struct {
		Name   string            `json:"name"`
		Lang   string            `json:"lang"`
		Seed   string            `json:"seed"`
		Env    map[string]string `json:"env"`
		Status int               `json:"status"`
		Lines  []string          `json:"lines"`
	} `json:"cases"`
	Helpers struct {
		Drafts     [][]any `json:"drafts"`
		Normalise  [][]any `json:"normalise"`
		Age        [][]any `json:"age"`
		Capitalize [][]any `json:"capitalize"`
		Late       [][]any `json:"late"`
	} `json:"helpers"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/admin_operations_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g golden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) != 5 || len(g.Seed) < 10 {
		t.Fatal("golden file is too small")
	}
	return g
}

func goldenNow(t *testing.T, g golden) time.Time {
	t.Helper()
	now, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	return now
}

// keep is golden.KEEP: the tables an "users" case seeds.
var keep = map[string]bool{"user_account": true, "legal_acceptance": true}

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_opspage_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			return
		}
		defer c.Close(context.Background())
		_, _ = c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)")
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}

func seedValue(t *testing.T, v any) any {
	t.Helper()
	switch x := v.(type) {
	case json.Number:
		n, err := x.Int64()
		if err != nil {
			t.Fatalf("seed number %s", x)
		}
		return n
	case string, nil:
		return x
	}
	t.Fatalf("seed value %T", v)
	return nil
}

// seed loads the golden rows: every table for "full", the KEEP tables for "users".
func seed(t *testing.T, pool *pgxpool.Pool, g golden, which string) {
	t.Helper()
	for _, table := range g.Seed {
		if which == "users" && !keep[table.Table] {
			continue
		}
		for _, row := range table.Rows {
			cols := make([]string, 0, len(row))
			for c := range row {
				cols = append(cols, c)
			}
			sort.Strings(cols)
			marks := make([]string, len(cols))
			args := make([]any, len(cols))
			for i, c := range cols {
				marks[i] = "$" + strconv.Itoa(i+1)
				args[i] = seedValue(t, row[c])
			}
			sql := "INSERT INTO " + table.Table + " (" + strings.Join(cols, ", ") + ") VALUES (" + strings.Join(marks, ", ") + ")"
			if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
}

// visibleLines is visible_lines in App/scripts/admin_operations_golden.py; keep the two in step.
var (
	dropRes = []*regexp.Regexp{regexp.MustCompile(`(?s)<!--.*?-->`), regexp.MustCompile(`(?is)<script\b.*?</script>`),
		regexp.MustCompile(`(?is)<style\b.*?</style>`), regexp.MustCompile(`(?is)<svg\b.*?</svg>`)}
	tokenRe = regexp.MustCompile(`<[^>]*>|[^<]+`)
	tagRe   = regexp.MustCompile(`^<[ \t\n\r\f\v]*(/?)([A-Za-z][A-Za-z0-9]*)`)
	attrRe  = regexp.MustCompile(`([^ \t\n\r\f\v=/>"']+)(?:[ \t\n\r\f\v]*=[ \t\n\r\f\v]*(?:"([^"]*)"|'([^']*)'|([^ \t\n\r\f\v>"']+)))?`)
	spaceRe = regexp.MustCompile(`[ \t\n\r\f\v]+`)
	kept    = map[string]bool{"id": true, "href": true, "action": true, "method": true, "name": true, "value": true,
		"type": true, "selected": true, "checked": true, "required": true, "for": true, "aria-current": true,
		"open": true, "disabled": true, "class": true, "data-label": true, "placeholder": true, "inputmode": true,
		"data-turbo": true, "aria-controls": true}
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
			value := strings.Trim(spaceRe.ReplaceAllString(html.UnescapeString(a[2]+a[3]+a[4]), " "), " ")
			attrs[strings.ToLower(a[1])] = attrVal{strings.Contains(a[0], "="), value}
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
		`<svg><path d="M0"/></svg><details class=" a   b " open><button disabled data-x="1">Go</button></details></div>` +
		`<div class="page-skeleton">skip</div>`
	want := []string{"<div class=ui-page>", "<a class=ui-ph-back x href=/b?a=1&b=2>", "T's", "bold", "<input name=_csrf type=hidden value=*>",
		"<input name=q required>", "<details class=a b open>", "<button disabled>", "Go"}
	if got := visibleLines(page); strings.Join(got, "\n") != strings.Join(want, "\n") {
		t.Fatalf("got %q", got)
	}
}

func testGetenv(g golden, env map[string]string) func(string) string {
	m := map[string]string{
		"UBYHOST_SECRET_KEY":      testSecret,
		"UBYHOST_TERMS_VERSION":   g.Versions["terms"],
		"UBYHOST_PRIVACY_VERSION": g.Versions["privacy"],
		"UBYHOST_DPA_VERSION":     g.Versions["dpa"],
	}
	for k, v := range env {
		m[k] = v
	}
	return func(k string) string { return m[k] }
}

// handler is what package auth's operationsAdmin does: _require_admin, then Serve.
func handler(pool *pgxpool.Pool, getenv func(string) string, now time.Time) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h, err := admingate.Require(w, r, pool, getenv, now)
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		if h == nil {
			return
		}
		if err := Serve(w, r, pool, getenv, now, h); err != nil {
			http.Error(w, err.Error(), 500)
		}
	})
}

func get(t *testing.T, h http.Handler, lang string, payload map[string]any, now time.Time) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest("GET", "/admin/operations", nil)
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	if payload != nil {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, now)})
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// TestPageMatchesPython renders each golden case with the Go handler and
// compares the visible lines with the ones Python rendered.
func TestPageMatchesPython(t *testing.T) {
	g := loadGolden(t)
	now := goldenNow(t, g)
	pools := map[string]*pgxpool.Pool{}
	for _, which := range []string{"full", "users"} {
		pools[which] = testPool(t)
		seed(t, pools[which], g, which)
	}
	for _, c := range g.Cases {
		rec := get(t, handler(pools[c.Seed], testGetenv(g, c.Env), now), c.Lang, map[string]any{"uid": 1, "sv": 1}, now)
		if rec.Code != c.Status {
			t.Errorf("%s: status %d, Python %d (%s)", c.Name, rec.Code, c.Status, rec.Body.String())
			continue
		}
		got := visibleLines(rec.Body.String())
		if len(got) < 250 {
			t.Errorf("%s: only %d lines", c.Name, len(got))
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
				lo := max(0, i-3)
				t.Errorf("%s: line %d is %q, Python %q (Go context %q)", c.Name, i, gl, wl, got[lo:min(len(got), i+1)])
				break
			}
		}
	}
}

// TestPageNeedsAdmin: a signed-out visitor goes to the login page and a host
// gets the 403 text, as _require_admin answers.
func TestPageNeedsAdmin(t *testing.T) {
	g := loadGolden(t)
	now := goldenNow(t, g)
	pool := testPool(t)
	seed(t, pool, g, "full")
	for i, doc := range []string{"terms", "privacy", "dpa"} { // host 2 has accepted, so the gate reaches the role check
		if _, err := pool.Exec(context.Background(), `INSERT INTO legal_acceptance (id, user_account_id, document, version,
			accepted_at, method) VALUES ($1, 2, $2, $3, '2026-01-01T00:00:00+00:00', 'clickwrap')`, 10+i, doc, g.Versions[doc]); err != nil {
			t.Fatal(err)
		}
	}
	h := handler(pool, testGetenv(g, nil), now)
	rec := get(t, h, "en", nil, now)
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/admin/operations" {
		t.Fatalf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	rec = get(t, h, "en", map[string]any{"uid": 2, "sv": 1}, now)
	if rec.Code != http.StatusForbidden || rec.Body.String() != "Administrators only." {
		t.Fatalf("host: %d %q", rec.Code, rec.Body.String())
	}
}

// TestDraftsMatchPython: controller_notification_draft byte for byte.
func TestDraftsMatchPython(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g, "full")
	incidents, err := LoadIncidents(context.Background(), pool)
	if err != nil {
		t.Fatal(err)
	}
	if len(incidents) != len(g.Helpers.Drafts) {
		t.Fatalf("%d incidents, Python %d", len(incidents), len(g.Helpers.Drafts))
	}
	for i, d := range g.Helpers.Drafts {
		if id := d[0].(json.Number).String(); id != strconv.FormatInt(incidents[i].ID, 10) {
			t.Errorf("incident %d: id %s, Python %s", i, strconv.FormatInt(incidents[i].ID, 10), id)
		}
		if got := Draft(incidents[i]); got != d[1].(string) {
			t.Errorf("incident %d draft:\n%s\nPython:\n%s", incidents[i].ID, got, d[1])
		}
	}
}

// TestHelpersMatchPython: normalise_question, age_minutes, capitalize and
// late_after_minutes on the golden's inputs.
func TestHelpersMatchPython(t *testing.T) {
	g := loadGolden(t)
	now := goldenNow(t, g)
	for _, c := range g.Helpers.Normalise {
		if got := ai.HavelNormaliseQuestion(c[0].(string)); got != c[1].(string) {
			t.Errorf("normalise(%q) = %q, Python %q", c[0], got, c[1])
		}
	}
	for _, c := range g.Helpers.Age {
		var in *string
		if s, ok := c[0].(string); ok {
			in = &s
		}
		got := ageMinutes(in, now)
		want, _ := c[1].(json.Number)
		switch {
		case want == "" && got != nil:
			t.Errorf("age(%v) = %d, Python None", c[0], *got)
		case want != "" && (got == nil || strconv.FormatInt(*got, 10) != want.String()):
			t.Errorf("age(%v) = %v, Python %s", c[0], got, want)
		}
	}
	for _, c := range g.Helpers.Capitalize {
		if got := pyCapitalize(c[0].(string)); got != c[1].(string) {
			t.Errorf("capitalize(%q) = %q, Python %q", c[0], got, c[1])
		}
	}
	for _, c := range g.Helpers.Late {
		in, _ := c[0].(json.Number).Int64()
		want, _ := c[1].(json.Number).Int64()
		if got := lateAfterMinutes(in); got != want {
			t.Errorf("late(%d) = %d, Python %d", in, got, want)
		}
	}
	if len(g.Helpers.Normalise) < 10 || len(g.Helpers.Age) < 10 {
		t.Fatal("helper cases missing")
	}
}

func TestOwnerIDs(t *testing.T) {
	s := func(v string) *string { return &v }
	for in, want := range map[string]string{
		`[2, 3]`: "[2 3]", `[]`: "[]", `not json`: "[]", `["4", 99]`: "[4 99]", `[3.9, true]`: "[3 1]",
		`[null]`: "[]", `[[1]]`: "[]", `"12"`: "[1 2]", `"1a"`: "[]", `5`: "[]", `{"1": 2}`: "[]", `[" 7 "]`: "[7]",
		`[1] x`: "[]",
	} {
		if got := fmt.Sprint(ownerIDs(s(in))); got != want {
			t.Errorf("ownerIDs(%s) = %s, want %s", in, got, want)
		}
	}
	if got := fmt.Sprint(ownerIDs(nil)); got != "[]" {
		t.Errorf("ownerIDs(nil) = %s", got)
	}
}

func TestCatalogHasPageKeys(t *testing.T) {
	for _, key := range []string{"ops.title", "ops.age.never", "incidents.mark", "notification.job_name.ical",
		"admin.tab.system", "customers.title", "guide.nav.faq", "guide.stays.add_title", "ops.havel.reason.fail"} {
		for _, lang := range []string{"en", "cs"} {
			if catalog[lang][key] == "" {
				t.Errorf("%s has no %s text", key, lang)
			}
		}
	}
}
