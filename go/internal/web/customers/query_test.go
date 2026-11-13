package customers

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// goldenFile is what App/scripts/admin_customers_golden.py wrote from the real
// Python. Fields are kept raw and compared as normalised JSON.
type goldenFile struct {
	Today    string                       `json:"today"`
	Versions map[string]string            `json:"versions"`
	Seed     []seedTable                  `json:"seed"`
	Filters  []json.RawMessage            `json:"filters_check"`
	List     []listCase                   `json:"list"`
	Summary  json.RawMessage              `json:"summary"`
	Missing  json.RawMessage              `json:"missing_email_count"`
	Detail   map[string]json.RawMessage   `json:"detail"`
	Account  map[string]json.RawMessage   `json:"account"`
	Consent  map[string]json.RawMessage   `json:"consent"`
	I18N     map[string]map[string]string `json:"i18n"`
	Cursor   [][2]json.RawMessage         `json:"cursor"`
	KC       [][2]json.RawMessage         `json:"kc"`
	Toggle   struct {
		Steps []toggleStep `json:"steps"`
	} `json:"toggle"`
}

type seedTable struct {
	Table string                       `json:"table"`
	Rows  []map[string]json.RawMessage `json:"rows"`
}

type listCase struct {
	Name   string          `json:"name"`
	Q      string          `json:"q"`
	State  string          `json:"state"`
	Plan   string          `json:"plan"`
	After  int64           `json:"after"`
	Before int64           `json:"before"`
	Values json.RawMessage `json:"values"`
	Result json.RawMessage `json:"result"`
}

type toggleStep struct {
	Name       string            `json:"name"`
	Method     string            `json:"method"`
	Path       string            `json:"path"`
	Lang       string            `json:"lang"`
	Target     int64             `json:"target"`
	Role       string            `json:"role"`
	Status     int               `json:"status"`
	Location   *string           `json:"location"`
	Body       *string           `json:"body"`
	CType      *string           `json:"content_type"`
	UserBefore json.RawMessage   `json:"user_before"`
	UserAfter  json.RawMessage   `json:"user_after"`
	AuditAdded []json.RawMessage `json:"audit_added"`
}

func loadGolden(t *testing.T) goldenFile {
	t.Helper()
	raw, err := os.ReadFile("testdata/admin_customers_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g goldenFile
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.List) < 40 || len(g.Seed) == 0 || len(g.Toggle.Steps) < 8 {
		t.Fatal("golden file is too small")
	}
	return g
}

// norm decodes JSON (numbers kept as written) and encodes it again, so two
// documents compare equal when they hold the same values.
func norm(t *testing.T, raw []byte) string {
	t.Helper()
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		t.Fatalf("bad JSON %q: %v", raw, err)
	}
	out, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return string(out)
}

func normValue(t *testing.T, v any) string {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return norm(t, raw)
}

func same(t *testing.T, what string, got any, want json.RawMessage) {
	t.Helper()
	if g, w := normValue(t, got), norm(t, want); g != w {
		t.Errorf("%s differs from Python\n got: %s\nwant: %s", what, g, w)
	}
}

// dbPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies the
// goose Up sections of App/migrations_pg and drops it at the end.
func dbPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := "ubyhost_go_customers_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
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

// seedValue turns one JSON value into a query argument.
func seedValue(t *testing.T, raw json.RawMessage) any {
	t.Helper()
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		t.Fatal(err)
	}
	if n, ok := v.(json.Number); ok {
		i, err := n.Int64()
		if err != nil {
			t.Fatalf("seed number %s is not an integer", n)
		}
		return i
	}
	return v
}

// seed inserts the golden rows, each with only the columns it lists.
func seed(t *testing.T, pool *pgxpool.Pool, g goldenFile) {
	t.Helper()
	for _, table := range g.Seed {
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
			sql := "INSERT INTO " + table.Table + " (" + strings.Join(cols, ", ") +
				") VALUES (" + strings.Join(marks, ", ") + ")"
			if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
}

func goldenToday(t *testing.T, g goldenFile) time.Time {
	t.Helper()
	today, err := time.Parse("2006-01-02", g.Today)
	if err != nil {
		t.Fatal(err)
	}
	return today
}

func TestFiltersCursorKCMatchPython(t *testing.T) {
	g := loadGolden(t)
	for _, raw := range g.Filters {
		var c [4]json.RawMessage
		if err := json.Unmarshal(raw, &c); err != nil {
			t.Fatal(err)
		}
		var q, s, p string
		_ = json.Unmarshal(c[0], &q)
		_ = json.Unmarshal(c[1], &s)
		_ = json.Unmarshal(c[2], &p)
		same(t, "filters("+s+")", NewFilters(q, s, p), c[3])
	}
	for _, c := range g.List {
		same(t, "filters of "+c.Name, NewFilters(c.Q, c.State, c.Plan), c.Values)
	}
	for _, c := range g.Cursor {
		var in string
		var want int64
		_ = json.Unmarshal(c[0], &in)
		if err := json.Unmarshal(c[1], &want); err != nil {
			t.Fatal(err)
		}
		if got := Cursor(in); got != want {
			t.Errorf("Cursor(%q) = %d, Python gives %d", in, got, want)
		}
	}
	for _, c := range g.KC {
		var in int64
		var want string
		if err := json.Unmarshal(c[0], &in); err != nil {
			t.Fatal(err)
		}
		_ = json.Unmarshal(c[1], &want)
		if got := KC(in); got != want {
			t.Errorf("KC(%d) = %q, Python gives %q", in, got, want)
		}
	}
}

func TestQueriesMatchPython(t *testing.T) {
	g := loadGolden(t)
	pool := dbPool(t)
	seed(t, pool, g)
	ctx := context.Background()
	today := goldenToday(t, g)

	for _, c := range g.List {
		got, err := Customers(ctx, pool, NewFilters(c.Q, c.State, c.Plan), c.After, c.Before, today)
		if err != nil {
			t.Fatalf("%s: %v", c.Name, err)
		}
		same(t, "list "+c.Name, got, c.Result)
	}
	sum, err := Summary(ctx, pool, today)
	if err != nil {
		t.Fatal(err)
	}
	same(t, "summary", sum, g.Summary)
	missing, err := MissingEmailCount(ctx, pool)
	if err != nil {
		t.Fatal(err)
	}
	same(t, "missing_email_count", missing, g.Missing)
	for id, want := range g.Detail {
		uid := int64(0)
		for _, ch := range id {
			uid = uid*10 + int64(ch-'0')
		}
		got, err := Detail(ctx, pool, uid)
		if err != nil {
			t.Fatalf("detail %s: %v", id, err)
		}
		same(t, "detail "+id, got, want)
		acct, err := BillingAccount(ctx, pool, uid)
		if err != nil {
			t.Fatalf("account %s: %v", id, err)
		}
		same(t, "account "+id, acct, g.Account[id])
		cons, err := ConsentCounts(ctx, pool, uid)
		if err != nil {
			t.Fatal(err)
		}
		if w, ok := g.Consent[id]; ok {
			same(t, "consent "+id, cons, w)
		}
	}
}
