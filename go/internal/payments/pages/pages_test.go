package pages

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"html"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// golden is testdata/golden.json, written by App/scripts/payments_pages_golden.py.
type golden struct {
	Secret  string            `json:"secret"`
	Env     map[string]string `json:"env"`
	Fixture []fixtureRow      `json:"fixture"`
	Links   map[string]string `json:"link_results"`
	Cases   []goldenCase      `json:"cases"`
	Writes  []goldenCase      `json:"writes"`
}

type fixtureRow struct {
	Table string         `json:"table"`
	Row   map[string]any `json:"row"`
}

type goldenCase struct {
	Name     string            `json:"name"`
	Method   string            `json:"method"`
	Path     string            `json:"path"`
	UID      int64             `json:"uid"`
	Lang     string            `json:"lang"`
	Mode     string            `json:"mode"`
	Form     map[string]string `json:"form"`
	Status   int               `json:"status"`
	Location string            `json:"location"`
	Title    string            `json:"title"`
	Body     string            `json:"body"`
	Page     *summaryData      `json:"page"`
	Rows     *rowsData         `json:"rows"`
}

type summaryData struct {
	Text   string   `json:"text"`
	Fields []string `json:"fields"`
	Links  []string `json:"links"`
}

type rowsData struct {
	Settings map[string]string `json:"settings"`
	Audit    []map[string]any  `json:"audit"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

// ---- summary: keep in step with summary() in payments_pages_golden.py -------

var (
	dropRes = []*regexp.Regexp{
		regexp.MustCompile(`(?is)<script\b.*?</script>`),
		regexp.MustCompile(`(?is)<style\b.*?</style>`),
		regexp.MustCompile(`(?is)<svg\b.*?</svg>`),
	}
	commentRe = regexp.MustCompile(`(?s)<!--.*?-->`)
	tagRe     = regexp.MustCompile(`<(/?)([a-zA-Z][a-zA-Z0-9-]*)((?:[^>"']|"[^"]*"|'[^']*')*)>`)
	attrRe    = regexp.MustCompile(`([a-zA-Z_:][-a-zA-Z0-9_:.]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?`)
)

var (
	fieldAttrs = []string{"name", "type", "value", "method", "action", "id", "for", "role"}
	fieldFlags = []string{"checked", "selected", "disabled", "required", "readonly", "open", "hidden"}
	fieldTags  = map[string]bool{"form": true, "input": true, "select": true, "option": true, "textarea": true, "button": true, "details": true, "label": true}
)

func bodyRegion(page string) string {
	start := strings.Index(page, `<div class="ui-page"`)
	if start < 0 {
		return ""
	}
	end := strings.Index(page[start:], `<div class="page-skeleton"`)
	if end < 0 {
		return ""
	}
	return page[start : start+end]
}

func summarise(page string) summaryData {
	region := bodyRegion(page)
	for _, re := range dropRes {
		region = re.ReplaceAllString(region, " ")
	}
	region = commentRe.ReplaceAllString(region, " ")
	out := summaryData{Fields: []string{}, Links: []string{}}
	for _, m := range tagRe.FindAllStringSubmatch(region, -1) {
		if m[1] != "" {
			continue
		}
		tag := strings.ToLower(m[2])
		attrs := map[string]*string{}
		for _, a := range attrRe.FindAllStringSubmatchIndex(m[3], -1) {
			name := strings.ToLower(m[3][a[2]:a[3]])
			var val *string
			for g := 4; g <= 8; g += 2 {
				if a[g] >= 0 {
					v := html.UnescapeString(m[3][a[g]:a[g+1]])
					val = &v
					break
				}
			}
			attrs[name] = val
		}
		if v, ok := attrs["name"]; ok && v != nil && *v == "_csrf" {
			c := "CSRF"
			attrs["value"] = &c
		}
		if v, ok := attrs["href"]; ok && tag == "a" {
			if v == nil {
				out.Links = append(out.Links, "")
			} else {
				out.Links = append(out.Links, *v)
			}
		}
		if fieldTags[tag] {
			parts := []string{tag}
			for _, k := range fieldAttrs {
				if v := attrs[k]; v != nil {
					parts = append(parts, k+"="+*v)
				}
			}
			for _, k := range fieldFlags {
				if _, ok := attrs[k]; ok {
					parts = append(parts, k)
				}
			}
			out.Fields = append(out.Fields, strings.Join(parts, " "))
		}
	}
	text := html.UnescapeString(tagRe.ReplaceAllString(region, " "))
	out.Text = strings.Join(strings.FieldsFunc(text, pySpace), " ")
	return out
}

var titleRe = regexp.MustCompile(`(?s)<title>(.*?)</title>`)

// ---- database ---------------------------------------------------------------------

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_paypages_%d", time.Now().UnixNano())
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
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
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
	files, err := filepath.Glob("../../../../App/migrations_pg/*.sql")
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

func seed(t *testing.T, pool *pgxpool.Pool, rows []fixtureRow) {
	t.Helper()
	ctx := context.Background()
	tables := map[string]bool{}
	for _, fr := range rows {
		cols := make([]string, 0, len(fr.Row))
		for c := range fr.Row {
			cols = append(cols, c)
		}
		sort.Strings(cols)
		marks := make([]string, len(cols))
		vals := make([]any, len(cols))
		for i, c := range cols {
			marks[i] = fmt.Sprintf("$%d", i+1)
			v := fr.Row[c]
			if f, ok := v.(float64); ok && f == float64(int64(f)) {
				v = int64(f)
			}
			vals[i] = v
		}
		q := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", fr.Table, strings.Join(cols, ", "), strings.Join(marks, ", "))
		if _, err := pool.Exec(ctx, q, vals...); err != nil {
			t.Fatalf("%s: %v", fr.Table, err)
		}
		if _, ok := fr.Row["id"]; ok {
			tables[fr.Table] = true
		}
	}
	for table := range tables {
		if _, err := pool.Exec(ctx, fmt.Sprintf(`SELECT setval(pg_get_serial_sequence('%s', 'id'), 10000)`, table)); err != nil {
			t.Fatalf("setval %s: %v", table, err)
		}
	}
}

var newID = regexp.MustCompile(`"id": "[0-9a-f]{8}"`)

func readRows(t *testing.T, pool *pgxpool.Pool) rowsData {
	t.Helper()
	ctx := context.Background()
	out := rowsData{Settings: map[string]string{}, Audit: []map[string]any{}}
	rows, err := pool.Query(ctx, `SELECT key, COALESCE(value, '') FROM settings WHERE key LIKE 'payment_services:%' ORDER BY key`)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var k, v string
		if err := rows.Scan(&k, &v); err != nil {
			t.Fatal(err)
		}
		out.Settings[k] = newID.ReplaceAllString(v, `"id": "<new>"`)
	}
	rows.Close()
	rows, err = pool.Query(ctx, `SELECT actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit
		WHERE action = 'payments_terms_accepted' ORDER BY owner_user_id, id`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	for rows.Next() {
		var (
			actor, action, detail string
			owner                 *int64
			actorID, imp          *int64
		)
		if err := rows.Scan(&actor, &action, &detail, &owner, &actorID, &imp); err != nil {
			t.Fatal(err)
		}
		num := func(p *int64) any {
			if p == nil {
				return nil
			}
			return float64(*p)
		}
		out.Audit = append(out.Audit, map[string]any{"actor": actor, "action": action, "detail": detail,
			"owner_user_id": num(owner), "actor_user_id": num(actorID), "impersonator_user_id": num(imp)})
	}
	return out
}

// ---- requests ---------------------------------------------------------------------

// fakeLinks answers SendPaymentLink from golden.json's link_results.
type fakeLinks struct{ results map[string]string }

func (f *fakeLinks) SendPaymentLink(_ context.Context, id int64) (string, error) {
	v := f.results[fmt.Sprint(id)]
	if v == "STRIPE_OFF" {
		return "", payments.ErrStripeOff
	}
	return v, nil
}

const csrfCookie = "golden-csrf-nonce"

func csrfToken(t *testing.T, secret string, now time.Time) string {
	t.Helper()
	sum := sha256.Sum256([]byte(csrfCookie))
	tok, err := secure.NewTimedSerializer(secret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, now)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

func newMux(pool *pgxpool.Pool, g golden, mode string, links payments.LinkSender) *http.ServeMux {
	env := func(k string) string {
		if k == "UBYHOST_STRIPE_MODE" {
			return mode
		}
		return g.Env[k]
	}
	mux := http.NewServeMux()
	mux.Handle("GET /payments", OverviewHandler(pool, env, time.Now))
	mux.Handle("GET /payments/new", NewHandler(pool, env, time.Now))
	mux.Handle("POST /payments/services", ServiceAddHandler(pool, env, time.Now))
	mux.Handle("POST /payments/services/{id}/delete", ServiceDeleteHandler(pool, env, time.Now))
	mux.Handle("GET /payments/requests/{id}/share", ShareHandler(pool, env, time.Now, links))
	mux.Handle("GET /payments/consent", ConsentHandler(pool, env, time.Now))
	mux.Handle("POST /payments/consent", ConsentAcceptHandler(pool, env, time.Now))
	return mux
}

func call(t *testing.T, pool *pgxpool.Pool, g golden, c goldenCase, links payments.LinkSender) *httptest.ResponseRecorder {
	t.Helper()
	now := time.Now()
	var req *http.Request
	if c.Method == http.MethodPost {
		form := url.Values{}
		for k, v := range c.Form {
			form.Set(k, v)
		}
		form.Set("_csrf", csrfToken(t, g.Secret, now))
		req = httptest.NewRequest(c.Method, c.Path, strings.NewReader(form.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfCookie})
	} else {
		req = httptest.NewRequest(c.Method, c.Path, nil)
	}
	req.Host = "testserver"
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: c.Lang})
	if c.UID != 0 {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(g.Secret,
			map[string]any{"uid": c.UID, "sv": int64(0), "iat": now.Unix(), "rf": now.Unix()}, now)})
	}
	rec := httptest.NewRecorder()
	newMux(pool, g, c.Mode, links).ServeHTTP(rec, req)
	return rec
}

func check(t *testing.T, c goldenCase, rec *httptest.ResponseRecorder) {
	t.Helper()
	if rec.Code != c.Status {
		t.Fatalf("status %d, Python %d (Location %q)", rec.Code, c.Status, rec.Header().Get("Location"))
	}
	if got := rec.Header().Get("Location"); got != c.Location {
		t.Errorf("Location\n go %q\n py %q", got, c.Location)
	}
	body := rec.Body.String()
	if c.Page == nil {
		if c.Status != http.StatusSeeOther && body != c.Body {
			t.Errorf("body %q, Python %q", body, c.Body)
		}
		return
	}
	if m := titleRe.FindStringSubmatch(body); m == nil || html.UnescapeString(strings.TrimSpace(m[1])) != html.UnescapeString(c.Title) {
		t.Errorf("title %v, Python %q", m, c.Title)
	}
	got := summarise(body)
	if got.Text != c.Page.Text {
		t.Errorf("text\n go %s\n py %s", got.Text, c.Page.Text)
	}
	if !reflect.DeepEqual(got.Fields, c.Page.Fields) {
		t.Errorf("fields\n go %q\n py %q", got.Fields, c.Page.Fields)
	}
	if !reflect.DeepEqual(got.Links, c.Page.Links) {
		t.Errorf("links\n go %q\n py %q", got.Links, c.Page.Links)
	}
}

// TestGoldenMatchesPython runs every Python case on the Go handlers: the same
// status, Location, title, visible text, form fields and links, and after
// each write the same payment_services settings and consent audit rows.
func TestGoldenMatchesPython(t *testing.T) {
	pool := testPool(t)
	g := loadGolden(t)
	seed(t, pool, g.Fixture)
	links := &fakeLinks{results: g.Links}
	if len(g.Cases) == 0 || len(g.Writes) == 0 {
		t.Fatal("golden.json has no cases")
	}
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) { check(t, c, call(t, pool, g, c, links)) })
	}
	for _, c := range g.Writes {
		ok := t.Run(c.Name, func(t *testing.T) {
			check(t, c, call(t, pool, g, c, links))
			got := readRows(t, pool)
			want := *c.Rows
			if !reflect.DeepEqual(got.Settings, want.Settings) {
				t.Errorf("settings\n go %q\n py %q", got.Settings, want.Settings)
			}
			if !reflect.DeepEqual(got.Audit, want.Audit) {
				t.Errorf("audit\n go %v\n py %v", got.Audit, want.Audit)
			}
		})
		if !ok {
			break // later writes build on this one
		}
	}
}

// TestPythonJSON: json.loads then json.dumps(ensure_ascii=False), as
// payment_services rewrites the setting (expected text from Python 3).
func TestPythonJSON(t *testing.T) {
	raw := `[{"id": "a", "n": 1.0, "e": 1e20, "f": 0.00001, "g": 123456789012345678, "h": 2.5e-3, "s": "<&> \u0001\\\"é", "z": null, "b": true, "x": [1, {"k": -0}], "id": "b"}]`
	want := `[{"id": "b", "n": 1.0, "e": 1e+20, "f": 1e-05, "g": 123456789012345678, "h": 0.0025, "s": "<&>` + " " + `\u0001\\\"é", "z": null, "b": true, "x": [1, {"k": 0}]}]`
	n, err := parseJSON(raw)
	if err != nil {
		t.Fatal(err)
	}
	var b bytes.Buffer
	n.dump(&b)
	if b.String() != want {
		t.Errorf("dump\n got %s\nwant %s", b.String(), want)
	}
	for _, bad := range []string{"{not json", "[1] 2", ""} {
		if _, err := parseJSON(bad); err == nil {
			t.Errorf("%q parsed", bad)
		}
	}
}

// TestDateCZ is validation.fmt_date (values checked against Python).
func TestDateCZ(t *testing.T) {
	for in, want := range map[string]string{
		"2026-11-05T10:00:00+00:00": "05.11.2026", "2026-1-5": "05.01.2026", "2026-02-30": "2026-02-30",
		"": "", "abc": "abc", "2026-11-05": "05.11.2026",
	} {
		if got := dateCZ(in); got != want {
			t.Errorf("dateCZ(%q) = %q, want %q", in, got, want)
		}
	}
}

var hrefRe = regexp.MustCompile(`(?i)href\s*=\s*"([^"]*)"`)

// TestShareNeverLinksJavascript: a stored link or guest e-mail that is a
// javascript: URL never becomes an href (brief 1353, until 1381's safeHref).
func TestShareNeverLinksJavascript(t *testing.T) {
	pool := testPool(t)
	g := loadGolden(t)
	seed(t, pool, g.Fixture)
	if _, err := pool.Exec(context.Background(), `UPDATE payment_request SET guest_email = 'javascript:alert(1)' WHERE id = 72`); err != nil {
		t.Fatal(err)
	}
	links := &fakeLinks{results: map[string]string{"72": "javascript:alert(1)//"}}
	c := goldenCase{Method: http.MethodGet, Path: "/payments/requests/72/share", UID: 2, Lang: "en", Mode: "test"}
	rec := call(t, pool, g, c, links)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	hrefs := hrefRe.FindAllStringSubmatch(rec.Body.String(), -1)
	if len(hrefs) == 0 {
		t.Fatal("no links")
	}
	for _, m := range hrefs {
		if strings.HasPrefix(strings.ToLower(strings.TrimSpace(html.UnescapeString(m[1]))), "javascript:") {
			t.Errorf("javascript href %q", m[1])
		}
	}
	if !strings.Contains(rec.Body.String(), `href="mailto:javascript%3Aalert%281%29?subject=`) {
		t.Error("mailto link missing or not encoded")
	}
}

// TestRefusals: Go-only edges the golden cannot record.
func TestRefusals(t *testing.T) {
	pool := testPool(t)
	g := loadGolden(t)
	seed(t, pool, g.Fixture)
	links := &fakeLinks{results: g.Links}
	before := readRows(t, pool)

	// FastAPI answers 422 for a non-integer id; Go answers 404.
	rec := call(t, pool, g, goldenCase{Method: http.MethodGet, Path: "/payments/requests/abc/share", UID: 2, Lang: "en", Mode: "test"}, links)
	if rec.Code != http.StatusNotFound {
		t.Errorf("non-integer id: status %d", rec.Code)
	}

	// A POST without a valid token changes nothing and never reaches /payments.
	for _, path := range []string{"/payments/services", "/payments/services/svc-a/delete", "/payments/consent"} {
		req := httptest.NewRequest(http.MethodPost, path, strings.NewReader("name=X&amount_czk=5&agree=1&_csrf=bad"))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Host = "testserver"
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfCookie})
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(g.Secret,
			map[string]any{"uid": int64(2), "sv": int64(0), "iat": time.Now().Unix()}, time.Now())})
		rec := httptest.NewRecorder()
		newMux(pool, g, "test", links).ServeHTTP(rec, req)
		if strings.HasPrefix(rec.Header().Get("Location"), "/payments") {
			t.Errorf("%s: bad csrf redirected to %q", path, rec.Header().Get("Location"))
		}
	}
	if after := readRows(t, pool); !reflect.DeepEqual(before, after) {
		t.Error("a refused POST changed rows")
	}
}
