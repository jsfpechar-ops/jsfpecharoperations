package exports

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// golden is testdata/exports_golden.json, written by App/scripts/exports_golden.py.
type golden struct {
	Secret   string `json:"secret"`
	DataKeys string `json:"data_keys"`
	Now      string `json:"now"`
	Seed     []struct {
		Table   string   `json:"table"`
		Columns []string `json:"columns"`
		Rows    [][]any  `json:"rows"`
	} `json:"seed"`
	Photos []string     `json:"photos"`
	Cases  []goldenCase `json:"cases"`
}

type goldenCase struct {
	Name    string            `json:"name"`
	Path    string            `json:"path"`
	Session map[string]int64  `json:"session"`
	Lang    *string           `json:"lang"`
	Status  int               `json:"status"`
	Headers map[string]string `json:"headers"`
	Audit   [][]any           `json:"audit"`
	Zip     [][]any           `json:"zip"`
	BodyB64 *string           `json:"body_b64"`
}

// comparedHeaders is HEADERS in the golden script.
var comparedHeaders = []string{"content-type", "content-disposition", "location", "cache-control"}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/exports_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	return g
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
	name := "ubyhost_go_exports_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
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

// value turns a JSON seed cell into a pgx argument.
func value(v any) any {
	if n, ok := v.(json.Number); ok {
		i, err := n.Int64()
		if err == nil {
			return i
		}
		return n.String()
	}
	return v
}

func seedGolden(t *testing.T, pool *pgxpool.Pool, g golden) {
	t.Helper()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		query := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table.Table,
			strings.Join(table.Columns, ", "), strings.Join(marks, ", "))
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = value(v)
			}
			if _, err := pool.Exec(context.Background(), query, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
}

// auditSince reads the audit rows after id as the golden lists them.
func auditSince(t *testing.T, pool *pgxpool.Pool, after int64) ([][]any, int64) {
	t.Helper()
	rows, err := pool.Query(context.Background(), `SELECT id, at, actor, action, detail, owner_user_id,
		actor_user_id, impersonator_user_id FROM audit WHERE id > $1 ORDER BY id`, after)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out [][]any
	last := after
	for rows.Next() {
		var id int64
		var at, action string
		var actor, detail *string
		var owner, actorID, imp *int64
		if err := rows.Scan(&id, &at, &actor, &action, &detail, &owner, &actorID, &imp); err != nil {
			t.Fatal(err)
		}
		last = id
		out = append(out, []any{at, deref(actor), action, deref(detail), num(owner), num(actorID), num(imp)})
	}
	return out, last
}

func deref(p *string) any {
	if p == nil {
		return nil
	}
	return *p
}

func num(p *int64) any {
	if p == nil {
		return nil
	}
	return json.Number(fmt.Sprint(*p))
}

func zipEntries(t *testing.T, body []byte) [][]any {
	t.Helper()
	zr, err := zip.NewReader(bytes.NewReader(body), int64(len(body)))
	if err != nil {
		t.Fatal(err)
	}
	var out [][]any
	for _, f := range zr.File {
		rc, err := f.Open()
		if err != nil {
			t.Fatal(err)
		}
		var b bytes.Buffer
		_, _ = b.ReadFrom(rc)
		rc.Close()
		out = append(out, []any{f.Name, json.Number(fmt.Sprint(f.Method)), base64.StdEncoding.EncodeToString(b.Bytes())})
	}
	return out
}

func TestGoldenParity(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	seedGolden(t, pool, g)
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	dataDir := t.TempDir()
	env := map[string]string{
		"UBYHOST_SECRET_KEY": g.Secret,
		"UBYHOST_DATA_KEYS":  g.DataKeys,
		"UBYHOST_DATA_DIR":   dataDir,
	}
	// Passport photo files the golden script wrote (file names only).
	if err := os.MkdirAll(filepath.Join(dataDir, "passport_photos"), 0o700); err != nil {
		t.Fatal(err)
	}
	for _, name := range g.Photos {
		if err := os.WriteFile(filepath.Join(dataDir, "passport_photos", name), []byte("x"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	getenv := func(k string) string { return env[k] }
	now := func() time.Time { return at }
	mux := http.NewServeMux()
	for _, route := range Routes(pool, getenv, now) {
		mux.Handle(route.Pattern, route.Handler)
	}
	_, last := auditSince(t, pool, 0)
	for _, c := range g.Cases {
		req := httptest.NewRequest(http.MethodGet, c.Path, nil)
		if c.Session != nil {
			iat := at.Unix()
			if c.Session["stale"] != 0 {
				iat -= 3600
			}
			payload := map[string]any{"uid": c.Session["uid"], "sv": int64(0), "iat": iat}
			if as, ok := c.Session["as"]; ok {
				payload["as"] = as
				payload["ast"] = at.Unix()
			}
			req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(g.Secret, payload, at)})
		}
		if c.Lang != nil {
			req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: *c.Lang})
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		if want, differs := goDiffers[c.Name]; differs {
			// Documented difference: Python 422 (FastAPI int validation), Go 404.
			if c.Status != http.StatusUnprocessableEntity || rec.Code != want || len(c.Audit) != 0 {
				t.Errorf("%s: python %d, go %d, want python 422 and go %d", c.Name, c.Status, rec.Code, want)
			}
			continue
		}
		if rec.Code != c.Status {
			t.Errorf("%s: status %d, want %d (%s)", c.Name, rec.Code, c.Status, rec.Body.String())
			continue
		}
		for _, h := range comparedHeaders {
			// A redirect: http.Redirect in hostweb adds a text/html type and
			// body that Starlette's RedirectResponse does not have.
			if rec.Code == http.StatusSeeOther && h == "content-type" {
				continue
			}
			if got, want := rec.Header().Get(h), c.Headers[h]; got != want {
				t.Errorf("%s: %s %q, want %q", c.Name, h, got, want)
			}
		}
		if c.Zip != nil {
			if got := zipEntries(t, rec.Body.Bytes()); !reflect.DeepEqual(got, c.Zip) {
				t.Errorf("%s: zip %v, want %v", c.Name, got, c.Zip)
			}
		} else if rec.Code != http.StatusSeeOther {
			want, _ := base64.StdEncoding.DecodeString(*c.BodyB64)
			if !bytes.Equal(rec.Body.Bytes(), want) {
				t.Errorf("%s: body %q, want %q", c.Name, rec.Body.String(), want)
			}
		}
		var got [][]any
		got, last = auditSince(t, pool, last)
		if len(got) != len(c.Audit) || (len(got) > 0 && !reflect.DeepEqual(got, c.Audit)) {
			t.Errorf("%s: audit %v, want %v", c.Name, got, c.Audit)
		}
	}
}

// goDiffers lists golden cases where Go answers differently on purpose: a
// non-integer id is a plain 404 in Go (no host layout for the HTML error
// page), where FastAPI answers a script with 422 JSON.
var goDiffers = map[string]int{
	"receipt_non_integer_id":    http.StatusNotFound,
	"xml_non_integer_id":        http.StatusNotFound,
	"stay_zip_non_integer_id":   http.StatusNotFound,
	"guest_json_non_integer_id": http.StatusNotFound,
}

func TestNoOwnerIsAServerError(t *testing.T) {
	rec := httptest.NewRecorder()
	if _, ok := requireOwner(rec, &session.Host{}); ok || rec.Code != http.StatusInternalServerError {
		t.Fatalf("nil owner: ok %v, status %d", ok, rec.Code)
	}
	rec = httptest.NewRecorder()
	h := &session.Host{Workspace: session.Account{ID: 7}}
	if owner, ok := requireOwner(rec, h); !ok || owner != int64(7) {
		t.Fatalf("owner %v ok %v", owner, ok)
	}
}

func TestFreshnessUsesTheFractionalClock(t *testing.T) {
	at := time.Unix(1_800_000_600, 0)
	h := &session.Host{Payload: map[string]any{"iat": int64(1_800_000_000)}}
	if !sessionIsFresh(h, at) {
		t.Error("exactly 600 s must be fresh")
	}
	if sessionIsFresh(h, at.Add(time.Millisecond)) {
		t.Error("600.001 s must be stale, as time.time() - iat > 600 in Python")
	}
}

func TestRoutesNeedNoPool(t *testing.T) {
	mux := http.NewServeMux()
	for _, route := range Routes(nil, func(string) string { return "" }, time.Now) {
		mux.Handle(route.Pattern, route.Handler)
	}
	// A non-.xml file under a submission is not an export: plain 404, no pool use.
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/submissions/1/notes.txt", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status %d", rec.Code)
	}
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/submissions/abc/receipt.pdf", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("non-integer id: status %d", rec.Code)
	}
}

func TestHelpers(t *testing.T) {
	if got := wordSafe("ABC/123 čx!!y"); got != "ABC_123_čx_y" {
		t.Errorf("wordSafe %q", got)
	}
	var b bytes.Buffer
	writeCSVRow(&b, []string{"a;b", `q"`, "x y", ""})
	if got := b.String(); got != "\"a;b\";\"q\"\"\";x y;\r\n" {
		t.Errorf("csv %q", got)
	}
	for in, want := range map[string]string{"=1": "'=1", "  -2": "'  -2", " x": "' x", "a": "a", "": ""} {
		if got := csvSafe(in); got != want {
			t.Errorf("csvSafe(%q) = %q", in, got)
		}
	}
	if _, ok := b64decode("abc"); ok {
		t.Error("bad padding decoded")
	}
	if got, ok := b64decode("aGk=\n"); !ok || string(got) != "hi" {
		t.Error("newline not dropped")
	}
}
