package properties

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
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

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const testSecret = "properties-test-secret-key-0123456789ab"

var testNow = time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC)

func testEnv(k string) string {
	return map[string]string{
		"UBYHOST_SECRET_KEY":      testSecret,
		"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example",
		"UBYHOST_TERMS_VERSION":   "t1",
		"UBYHOST_PRIVACY_VERSION": "p1",
		"UBYHOST_DPA_VERSION":     "d1",
	}[k]
}

func testClock() time.Time { return testNow }

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops it at the end. It skips
// when the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_properties_%d", time.Now().UnixNano())
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

// The cases file and the golden file written by App/tests/test_go_properties_actions.py.
type casesFile struct {
	Users    []int64                     `json:"users"`
	Seed     map[string][]map[string]any `json:"seed"`
	Cases    []actionCase                `json:"cases"`
	ReturnTo []returnToCase              `json:"return_to"`
	Readable []string                    `json:"readable"`
}

type actionCase struct {
	Name string         `json:"name"`
	User int64          `json:"user"`
	As   int64          `json:"as"`
	Lang string         `json:"lang"`
	Path string         `json:"path"`
	Form map[string]any `json:"form"`
}

type returnToCase struct {
	Value        string `json:"value"`
	Default      string `json:"default"`
	KeepFragment bool   `json:"keep_fragment"`
}

type goldenFile struct {
	Cases    []map[string]any `json:"cases"`
	ReturnTo []struct {
		returnToCase
		Want string `json:"want"`
	} `json:"return_to"`
	Readable []struct {
		Name string `json:"name"`
		Want string `json:"want"`
	} `json:"readable"`
}

func readJSON(t *testing.T, name string, into any) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", name))
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(into); err != nil {
		t.Fatalf("%s: %v", name, err)
	}
}

// sqlValue turns a JSON number into an int64 for pgx.
func sqlValue(v any) any {
	if n, ok := v.(json.Number); ok {
		i, err := n.Int64()
		if err != nil {
			panic(err)
		}
		return i
	}
	return v
}

func seedWorld(t *testing.T, pool *pgxpool.Pool, c *casesFile) {
	t.Helper()
	ctx := context.Background()
	for _, table := range []string{"user_account", "legal_entity", "invoice", "apartment", "ical_feed", "apartment_slug"} {
		for _, row := range c.Seed[table] {
			var cols, marks []string
			var args []any
			for col, v := range row {
				cols = append(cols, col)
				args = append(args, sqlValue(v))
				marks = append(marks, fmt.Sprintf("$%d", len(args)))
			}
			q := "INSERT INTO " + table + " (" + strings.Join(cols, ", ") + ") VALUES (" + strings.Join(marks, ", ") + ")"
			if _, err := pool.Exec(ctx, q, args...); err != nil {
				t.Fatalf("seed %s: %v", table, err)
			}
		}
	}
	// Login sends hosts without accepted terms to /account/accept; env versions are t1, p1, d1.
	for i, uid := range c.Users {
		for j, doc := range []struct{ name, version string }{{"terms", "t1"}, {"privacy", "p1"}, {"dpa", "d1"}} {
			if _, err := pool.Exec(ctx, `INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method)
				VALUES ($1, $2, $3, $4, NOW(), 'clickwrap')`, 130500+i*10+j, uid, doc.name, doc.version); err != nil {
				t.Fatal(err)
			}
		}
	}
}

// Normalisation of random and clock values, as in the Python test.
var (
	stampRE = regexp.MustCompile(`^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$`)
	tokenRE = regexp.MustCompile(`^[abcdefghijkmnopqrstuvwxyz23456789]{20}$`)
	pinRE   = regexp.MustCompile(`^[0-9]{6}$`)
	slugRE  = regexp.MustCompile(`^(.+)-[abcdefghijkmnopqrstuvwxyz23456789]{6}$`)
)

func normal(column string, v any) any {
	s, ok := v.(string)
	if !ok {
		return v
	}
	switch {
	case stampRE.MatchString(s):
		return "<ts>"
	case column == "permalink_token" && tokenRE.MatchString(s):
		return "<token>"
	case column == "permalink_pin" && pinRE.MatchString(s):
		return "<pin>"
	case column == "slug":
		if m := slugRE.FindStringSubmatch(s); m != nil {
			return m[1] + "-<code>"
		}
	}
	return s
}

type snapshotTable struct {
	name    string
	keys    []string
	columns []string
	where   string
}

var snapshotTables = []snapshotTable{
	{"legal_entity", []string{"id"}, []string{"id", "archived_at"}, "id BETWEEN 130000 AND 130999"},
	{"apartment", []string{"id"}, []string{"id", "archived_at", "active", "permalink_token", "permalink_pin"}, "id BETWEEN 130000 AND 130999"},
	{"ical_feed", []string{"id"}, []string{"id", "apartment_id"}, "id BETWEEN 130000 AND 130999"},
	{"apartment_slug", []string{"apartment_id", "slug"}, []string{"apartment_id", "slug", "is_current", "created_at"}, "apartment_id BETWEEN 130000 AND 130999"},
}

var auditColumns = []string{"actor", "action", "detail", "owner_user_id", "actor_user_id", "impersonator_user_id", "at"}

type state map[string]map[string]any

func readRows(t *testing.T, pool *pgxpool.Pool, q string, columns []string) []map[string]any {
	t.Helper()
	rows, err := pool.Query(context.Background(), q)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out []map[string]any
	for rows.Next() {
		vals, err := rows.Values()
		if err != nil {
			t.Fatal(err)
		}
		row := map[string]any{}
		for i, c := range columns {
			row[c] = normal(c, vals[i])
		}
		out = append(out, row)
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

func snapshot(t *testing.T, pool *pgxpool.Pool) state {
	t.Helper()
	st := state{}
	for _, tb := range snapshotTables {
		q := fmt.Sprintf("SELECT %s FROM %s WHERE %s ORDER BY %s", strings.Join(tb.columns, ", "), tb.name, tb.where, strings.Join(tb.keys, ", "))
		for _, row := range readRows(t, pool, q, tb.columns) {
			parts := []string{tb.name}
			for _, k := range tb.keys {
				parts = append(parts, fmt.Sprint(row[k]))
			}
			st[strings.Join(parts, "|")] = row
		}
	}
	q := "SELECT " + strings.Join(auditColumns, ", ") + " FROM audit WHERE owner_user_id BETWEEN 130000 AND 130999 ORDER BY id"
	for n, row := range readRows(t, pool, q, auditColumns) {
		st[fmt.Sprintf("audit|%03d", n)] = row
	}
	return st
}

func changes(before, after state) map[string]any {
	added := map[string]any{}
	changed := map[string]any{}
	removed := []string{}
	for key, row := range after {
		old, ok := before[key]
		if !ok {
			added[key] = row
			continue
		}
		diff := map[string]any{}
		for c, v := range row {
			if !reflect.DeepEqual(old[c], v) {
				diff[c] = []any{old[c], v}
			}
		}
		if len(diff) > 0 {
			changed[key] = diff
		}
	}
	for key := range before {
		if _, ok := after[key]; !ok {
			removed = append(removed, key)
		}
	}
	sort.Strings(removed)
	return map[string]any{"added": added, "changed": changed, "removed": removed}
}

func csrfToken(t *testing.T, cookie string) string {
	t.Helper()
	sum := sha256.Sum256([]byte(cookie))
	tok, err := secure.NewTimedSerializer(testSecret, "ubyhost-csrf").
		Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, testNow)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

const csrfCookie = "properties-test-csrf-cookie"

func newMux(pool *pgxpool.Pool) *http.ServeMux {
	mux := http.NewServeMux()
	Register(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, testEnv, testClock)
	return mux
}

// post sends form to path as host uid (0 means signed out; as > 0 is an admin
// inside that workspace, started now) with a valid CSRF token and the language
// cookie.
func post(t *testing.T, mux http.Handler, path string, uid, as int64, lang string, form url.Values) *httptest.ResponseRecorder {
	t.Helper()
	// A case with a form sends the token as the _csrf field, as the browser
	// forms do, so return_to must survive the CSRF body read; the others send
	// the header.
	header := len(form) == 0
	if !header {
		form.Set("_csrf", csrfToken(t, csrfCookie))
	}
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if header {
		req.Header.Set("x-csrf-token", csrfToken(t, csrfCookie))
	}
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfCookie})
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	if uid != 0 {
		payload := map[string]any{"uid": uid, "sv": int64(1), "iat": testNow.Unix()}
		if as != 0 {
			payload["as"] = as
			payload["ast"] = testNow.Unix()
		}
		token := session.Sign(testSecret, payload, testNow)
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: token})
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func formValues(t *testing.T, raw map[string]any) url.Values {
	t.Helper()
	form := url.Values{}
	for k, v := range raw {
		switch x := v.(type) {
		case string:
			form.Add(k, x)
		case []any:
			for _, item := range x {
				form.Add(k, item.(string))
			}
		default:
			t.Fatalf("form value %T", v)
		}
	}
	return form
}

// asJSON round-trips a value so numbers and nested maps compare like the golden.
func asJSON(t *testing.T, v any) any {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var out any
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatal(err)
	}
	return out
}

func TestActionsMatchPython(t *testing.T) {
	pool := testPool(t)
	var c casesFile
	var g goldenFile
	readJSON(t, "actions_cases.json", &c)
	readJSON(t, "actions_golden.json", &g)
	if len(g.Cases) != len(c.Cases) {
		t.Fatalf("golden has %d cases, cases file %d", len(g.Cases), len(c.Cases))
	}
	seedWorld(t, pool, &c)
	mux := newMux(pool)
	before := snapshot(t, pool)
	for i, tc := range c.Cases {
		rec := post(t, mux, tc.Path, tc.User, tc.As, tc.Lang, formValues(t, tc.Form))
		after := snapshot(t, pool)
		got := map[string]any{
			"name":     tc.Name,
			"status":   rec.Code,
			"location": rec.Header().Get("Location"),
			"changes":  changes(before, after),
		}
		before = after
		want := g.Cases[i]
		if !reflect.DeepEqual(asJSON(t, got), asJSON(t, want)) {
			gotJSON, _ := json.MarshalIndent(got, "", " ")
			wantJSON, _ := json.MarshalIndent(want, "", " ")
			t.Errorf("case %q differs\n got: %s\nwant: %s", tc.Name, gotJSON, wantJSON)
		}
	}
}

func TestReturnToMatchesPython(t *testing.T) {
	var g goldenFile
	readJSON(t, "actions_golden.json", &g)
	if len(g.ReturnTo) == 0 {
		t.Fatal("no return_to cases")
	}
	for _, tc := range g.ReturnTo {
		req := httptest.NewRequest(http.MethodPost, "/x", strings.NewReader(url.Values{"return_to": {tc.Value}}.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		_ = req.ParseForm()
		if got := formReturnTo(req, tc.Default, tc.KeepFragment); got != tc.Want {
			t.Errorf("return_to %q (default %q, keep fragment %v): got %q, want %q", tc.Value, tc.Default, tc.KeepFragment, got, tc.Want)
		}
	}
}

func TestReadableMatchesPython(t *testing.T) {
	var g goldenFile
	readJSON(t, "actions_golden.json", &g)
	if len(g.Readable) == 0 {
		t.Fatal("no readable cases")
	}
	for _, tc := range g.Readable {
		if got := generatedReadable(tc.Name); got != tc.Want {
			t.Errorf("name %q: got %q, want %q", tc.Name, got, tc.Want)
		}
	}
}

func TestRandomShapes(t *testing.T) {
	seen := map[string]bool{}
	for i := 0; i < 300; i++ {
		token, err := newPermalinkToken()
		if err != nil || !tokenRE.MatchString(token) {
			t.Fatalf("token %q: %v", token, err)
		}
		pin, err := newPermalinkPIN()
		if err != nil || !pinRE.MatchString(pin) {
			t.Fatalf("pin %q: %v", pin, err)
		}
		seen[token] = true
	}
	if len(seen) < 299 {
		t.Errorf("only %d distinct tokens in 300", len(seen))
	}
}

func TestCatalogHasEveryKey(t *testing.T) {
	raw, err := os.ReadFile("i18n_keys.txt")
	if err != nil {
		t.Fatal(err)
	}
	n := 0
	for _, line := range strings.Split(string(raw), "\n") {
		key := strings.TrimSpace(line)
		if key == "" || strings.HasPrefix(key, "#") {
			continue
		}
		n++
		for _, lang := range []string{"en", "cs"} {
			if text := catalog.T(lang, key, nil); text == key || text == "" {
				t.Errorf("%s has no %s text", key, lang)
			}
		}
	}
	if n == 0 {
		t.Fatal("no keys")
	}
}

func TestRegisterDoesNotTouchThePool(t *testing.T) {
	mux := newMux(nil)
	req := httptest.NewRequest(http.MethodGet, "/entities/1/archive", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET: code %d, want 405", rec.Code)
	}
}
