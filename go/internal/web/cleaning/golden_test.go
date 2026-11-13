package cleaning

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
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

const goldenSecret = "cleaning-test-secret-key-0123456789abcdef"

// goldenNow is 12:00 in Prague on the golden TODAY.
var goldenNow = time.Date(2026, 5, 10, 10, 0, 0, 0, time.UTC)

type goldenTable struct {
	Table   string   `json:"table"`
	Columns []string `json:"columns"`
	Encrypt []string `json:"encrypt"`
	Rows    [][]any  `json:"rows"`
}

type goldenCase struct {
	Name        string            `json:"name"`
	Method      string            `json:"method"`
	Path        string            `json:"path"`
	Query       string            `json:"query"`
	User        *int64            `json:"user"`
	LangCookie  *string           `json:"lang_cookie"`
	Form        map[string]string `json:"form"`
	CSRF        bool              `json:"csrf"`
	Private     bool              `json:"private"`
	Status      int               `json:"status"`
	Location    *string           `json:"location"`
	ContentType *string           `json:"content_type"`
	Body        string            `json:"body"`
}

type goldenFile struct {
	Today     string            `json:"today"`
	CSRFNonce string            `json:"csrf_nonce"`
	Versions  map[string]string `json:"versions"`
	Seed      []goldenTable     `json:"seed"`
	Cases     []goldenCase      `json:"cases"`
	Final     json.RawMessage   `json:"final"`
}

func goldenDataKey() string {
	return base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{9}, 32))
}

func goldenEnv(g goldenFile) func(string) string {
	env := map[string]string{
		"UBYHOST_SECRET_KEY":      goldenSecret,
		"UBYHOST_DATA_KEYS":       goldenDataKey(),
		"UBYHOST_DATA_KEY_LEGACY": "0",
		"UBYHOST_TERMS_VERSION":   g.Versions["terms"],
		"UBYHOST_PRIVACY_VERSION": g.Versions["privacy"],
		"UBYHOST_DPA_VERSION":     g.Versions["dpa"],
	}
	return func(k string) string { return env[k] }
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops it at the end.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := "ubyhost_go_cleaning_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
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
	files, _ := filepath.Glob("../../../../App/migrations_pg/*.sql")
	if len(files) == 0 {
		t.Fatal("no App/migrations_pg files found")
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

// seedValue turns a decoded JSON value into a query argument.
func seedValue(t *testing.T, v any) any {
	t.Helper()
	switch x := v.(type) {
	case nil:
		return nil
	case json.Number:
		n, err := x.Int64()
		if err != nil {
			t.Fatalf("seed number %v", x)
		}
		return n
	case string:
		return x
	}
	t.Fatalf("seed value %T", v)
	return nil
}

// goldenSeed inserts the golden rows, encrypting the "encrypt" columns with the
// test data key, and moves every id sequence past the seeded ids.
func goldenSeed(t *testing.T, pool *pgxpool.Pool, g goldenFile) {
	t.Helper()
	ctx := context.Background()
	mf, err := secure.NewMultiFernet([]byte(goldenDataKey()))
	if err != nil {
		t.Fatal(err)
	}
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := "INSERT INTO " + table.Table + " (" + strings.Join(table.Columns, ", ") +
			") VALUES (" + strings.Join(marks, ", ") + ")"
		secret := map[int]bool{}
		for _, c := range table.Encrypt {
			for i, col := range table.Columns {
				if col == c {
					secret[i] = true
				}
			}
		}
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = seedValue(t, v)
				if s, ok := args[i].(string); ok && secret[i] {
					tok, err := mf.EncryptString(s)
					if err != nil {
						t.Fatal(err)
					}
					args[i] = tok
				}
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
		if table.Columns[0] == "id" {
			if _, err := pool.Exec(ctx, "SELECT setval(pg_get_serial_sequence('"+table.Table+
				"', 'id'), (SELECT MAX(id) FROM "+table.Table+"))"); err != nil {
				t.Fatalf("setval %s: %v", table.Table, err)
			}
		}
	}
}

func goldenMux(pool *pgxpool.Pool, getenv func(string) string) *http.ServeMux {
	now := func() time.Time { return goldenNow }
	mux := http.NewServeMux()
	mux.Handle("GET /cleaning/schedule", ScheduleHandler(pool, getenv, now))
	mux.Handle("GET /cleaning/shared/{token}", SharedPageHandler(pool, getenv, now))
	mux.Handle("GET /cleaning/shared/{token}/schedule", SharedScheduleHandler(pool, getenv, now))
	mux.Handle("POST /cleaning/events/{id}/delete", DeleteHandler(pool, getenv, now))
	mux.Handle("POST /cleaning/shares/{id}/revoke", RevokeHandler(pool, getenv, now))
	return mux
}

func goldenRequest(t *testing.T, g goldenFile, c goldenCase) *http.Request {
	t.Helper()
	target := c.Path
	if c.Query != "" {
		target += "?" + c.Query
	}
	var body io.Reader
	form := url.Values{}
	for k, v := range c.Form {
		form.Set(k, v)
	}
	if c.CSRF {
		sum := sha256.Sum256([]byte(g.CSRFNonce))
		tok, err := secure.NewTimedSerializer(goldenSecret, "ubyhost-csrf").Dumps(
			map[string]any{"nonce": hex.EncodeToString(sum[:])}, goldenNow)
		if err != nil {
			t.Fatal(err)
		}
		form.Set("_csrf", tok)
	}
	if c.Method == http.MethodPost {
		body = strings.NewReader(form.Encode())
	}
	req := httptest.NewRequest(c.Method, target, body)
	if c.Method == http.MethodPost {
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	}
	if c.User != nil {
		req.AddCookie(&http.Cookie{Name: session.CookieName,
			Value: session.Sign(goldenSecret, map[string]any{"uid": *c.User, "sv": 1, "iat": goldenNow.Unix()}, goldenNow)})
	}
	if c.LangCookie != nil {
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: *c.LangCookie})
	}
	if c.CSRF {
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: g.CSRFNonce})
	}
	return req
}

var (
	spaceRE = regexp.MustCompile(`\s+`)
	tagRE   = regexp.MustCompile(`\s*([<>])\s*`)
	csrfRE  = regexp.MustCompile(`name="_csrf" value="[^"]*"`)
)

// normaliseHTML collapses whitespace, drops it next to tag brackets and blanks
// the CSRF form value, which is random in Python and empty in Go.
func normaliseHTML(s string) string {
	s = csrfRE.ReplaceAllString(s, `name="_csrf" value=""`)
	s = spaceRE.ReplaceAllString(s, " ")
	return strings.TrimSpace(tagRE.ReplaceAllString(s, "$1"))
}

// jsonTokens lists the tokens of a JSON text in order, so key order counts.
// The value of a "listHtml" key is compared after normaliseHTML.
func jsonTokens(t *testing.T, raw string) []string {
	t.Helper()
	dec := json.NewDecoder(strings.NewReader(raw))
	dec.UseNumber()
	var out []string
	listNext := false
	for {
		tok, err := dec.Token()
		if err == io.EOF {
			return out
		}
		if err != nil {
			t.Fatalf("bad JSON %v: %.200s", err, raw)
		}
		s := fmt.Sprintf("%T:%v", tok, tok)
		if str, ok := tok.(string); ok && listNext {
			s = "html:" + normaliseHTML(str)
		}
		listNext = false
		if str, ok := tok.(string); ok && str == "listHtml" {
			listNext = true
		}
		out = append(out, s)
	}
}

func firstDiff(a, b []string) string {
	for i := 0; i < len(a) && i < len(b); i++ {
		if a[i] != b[i] {
			if strings.HasPrefix(a[i], "html:") && strings.HasPrefix(b[i], "html:") {
				return fmt.Sprintf("token %d (listHtml) %s", i, textDiff(a[i], b[i]))
			}
			return fmt.Sprintf("token %d:\n got: %.600s\nwant: %.600s", i, a[i], b[i])
		}
	}
	return fmt.Sprintf("lengths %d and %d", len(a), len(b))
}

func textDiff(got, want string) string {
	i := 0
	for i < len(got) && i < len(want) && got[i] == want[i] {
		i++
	}
	from := i - 120
	if from < 0 {
		from = 0
	}
	cut := func(s string) string {
		if i+240 < len(s) {
			return s[from : i+240]
		}
		return s[from:]
	}
	return fmt.Sprintf("byte %d:\n got: …%s\nwant: …%s", i, cut(got), cut(want))
}

func loadGolden(t *testing.T) goldenFile {
	t.Helper()
	raw, err := os.ReadFile("testdata/cleaning_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g goldenFile
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 30 || len(g.Seed) == 0 {
		t.Fatal("golden file has too few cases or no seed")
	}
	return g
}

// TestCleaningMatchesPython seeds the golden rows, sends every golden request,
// in order, to the Go handlers and compares each answer with what the Python
// routes answered on the same rows, then the cleaning rows they left behind.
func TestCleaningMatchesPython(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	goldenSeed(t, pool, g)
	getenv := goldenEnv(g)
	mux := goldenMux(pool, getenv)
	for _, c := range g.Cases {
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, goldenRequest(t, g, c))
		if rec.Code != c.Status {
			t.Errorf("%s: status %d, Python %d: %.300s", c.Name, rec.Code, c.Status, rec.Body.String())
			continue
		}
		if c.Location != nil && rec.Header().Get("Location") != *c.Location {
			t.Errorf("%s: location %q, Python %q", c.Name, rec.Header().Get("Location"), *c.Location)
		}
		if c.Private {
			for k, v := range map[string]string{"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
				"X-Robots-Tag": "noindex, nofollow"} {
				if got := rec.Header().Get(k); got != v {
					t.Errorf("%s: %s %q, want %q", c.Name, k, got, v)
				}
			}
		}
		if c.Status >= 300 && c.Status < 400 {
			continue
		}
		if c.ContentType != nil && rec.Header().Get("Content-Type") != *c.ContentType {
			t.Errorf("%s: content type %q, Python %q", c.Name, rec.Header().Get("Content-Type"), *c.ContentType)
		}
		if strings.HasPrefix(rec.Header().Get("Content-Type"), "text/html") {
			if got, want := normaliseHTML(rec.Body.String()), normaliseHTML(c.Body); got != want {
				t.Errorf("%s: page differs from Python at %s", c.Name, textDiff(got, want))
			}
			continue
		}
		got, want := jsonTokens(t, rec.Body.String()), jsonTokens(t, c.Body)
		if strings.Join(got, "\x00") != strings.Join(want, "\x00") {
			t.Errorf("%s: JSON differs from Python at %s", c.Name, firstDiff(got, want))
		}
	}
	if got, want := goldenFinal(t, pool), canonical(t, g.Final); got != want {
		t.Errorf("final rows differ\n got: %s\nwant: %s", got, want)
	}
}

// goldenFinal reads the rows the golden script records at the end, as
// canonical JSON (keys sorted).
func goldenFinal(t *testing.T, pool *pgxpool.Pool) string {
	t.Helper()
	ctx := context.Background()
	rows, err := pool.Query(ctx, `SELECT id, apartment_id, source_reservation_id, source_date, scheduled_date,
		state, revision, overridden FROM cleaning_event ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	events := []map[string]any{}
	for rows.Next() {
		var id, apartment, revision, overridden int64
		var source *int64
		var sourceDate *string
		var day, state string
		if err := rows.Scan(&id, &apartment, &source, &sourceDate, &day, &state, &revision, &overridden); err != nil {
			t.Fatal(err)
		}
		events = append(events, map[string]any{"id": id, "apartment_id": apartment, "source_reservation_id": source,
			"source_date": sourceDate, "scheduled_date": day, "state": state, "revision": revision, "overridden": overridden})
	}
	rows.Close()
	rows, err = pool.Query(ctx, `SELECT id, revoked_at IS NOT NULL FROM cleaning_share ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	shares := []map[string]any{}
	for rows.Next() {
		var id int64
		var revoked bool
		if err := rows.Scan(&id, &revoked); err != nil {
			t.Fatal(err)
		}
		shares = append(shares, map[string]any{"id": id, "revoked": revoked})
	}
	rows.Close()
	raw, _ := json.Marshal(map[string]any{"cleaning_event": events, "cleaning_share": shares})
	return canonical(t, raw)
}

func canonical(t *testing.T, raw []byte) string {
	t.Helper()
	var v any
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&v); err != nil {
		t.Fatal(err)
	}
	out, _ := json.Marshal(v)
	return string(out)
}
