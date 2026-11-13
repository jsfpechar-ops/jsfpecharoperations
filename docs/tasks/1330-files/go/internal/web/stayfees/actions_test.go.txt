package stayfees

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// goldenSecret is the UBYHOST_SECRET_KEY App/scripts/stay_fee_actions_golden.py runs with.
const goldenSecret = "golden-secret-key-not-for-real-use"

type goldenTable struct {
	Table   string   `json:"table"`
	Columns []string `json:"columns"`
	Rows    [][]any  `json:"rows"`
}

type goldenCase struct {
	Name               string            `json:"name"`
	Method             string            `json:"method"`
	Path               string            `json:"path"`
	Form               map[string]string `json:"form"`
	Who                *string           `json:"who"`
	Lang               *string           `json:"lang"`
	IdentityHidden     bool              `json:"identity_hidden"`
	Status             int               `json:"status"`
	Location           *string           `json:"location"`
	ContentType        *string           `json:"content_type"`
	ContentDisposition *string           `json:"content_disposition"`
	CacheControl       *string           `json:"cache_control"`
	Body               *string           `json:"body"`
	Changed            map[string]any    `json:"changed"`
}

type golden struct {
	Now     string         `json:"now"`
	Seed    []goldenTable  `json:"seed"`
	Initial map[string]any `json:"initial"`
	Cases   []goldenCase   `json:"cases"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/actions_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	return g
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL and
// applies the Postgres migrations, as go/internal/pushweb does.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_stayfees_%d", time.Now().UnixNano())
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
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("migration %s: %v", f, err)
		}
	}
	return pool
}

// seedValue turns a golden JSON value into a query argument: whole numbers
// become int64, {"b64": ...} becomes bytes.
func seedValue(t *testing.T, v any) any {
	switch x := v.(type) {
	case json.Number:
		n, err := x.Int64()
		if err != nil {
			t.Fatalf("seed number %v", x)
		}
		return n
	case map[string]any:
		raw, err := base64.StdEncoding.DecodeString(x["b64"].(string))
		if err != nil {
			t.Fatal(err)
		}
		return raw
	}
	return v
}

func seed(t *testing.T, pool *pgxpool.Pool, g golden) {
	t.Helper()
	ctx := context.Background()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := "INSERT INTO " + table.Table + " (" + strings.Join(table.Columns, ", ") + ") VALUES (" + strings.Join(marks, ", ") + ")"
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = seedValue(t, v)
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
	// acceptance.pending is switched off in the golden script; here every
	// account has accepted the current versions.
	for _, uid := range []int{1, 2, 3} {
		for _, doc := range []string{"terms", "privacy", "dpa"} {
			if _, err := pool.Exec(ctx,
				`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES ($1, $2, '1.7', '2026-01-01', 'clickwrap')`,
				uid, doc); err != nil {
				t.Fatal(err)
			}
		}
	}
}

// rows reads a query as JSON-shaped maps.
func rows(t *testing.T, pool *pgxpool.Pool, sql string) []any {
	t.Helper()
	rs, err := pool.Query(context.Background(), sql)
	if err != nil {
		t.Fatal(err)
	}
	defer rs.Close()
	out := []any{}
	fields := rs.FieldDescriptions()
	for rs.Next() {
		values, err := rs.Values()
		if err != nil {
			t.Fatal(err)
		}
		m := map[string]any{}
		for i, f := range fields {
			m[f.Name] = values[i]
		}
		out = append(out, m)
	}
	if err := rs.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

// snapshot is _snapshot in the golden script.
func snapshot(t *testing.T, pool *pgxpool.Pool, keys *secure.MultiFernet) map[string]any {
	t.Helper()
	fee := strings.Join(feeCopyFields, ", ")
	snap := map[string]any{
		"audit":               rows(t, pool, `SELECT at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id`),
		"stay_fee_adjustment": rows(t, pool, `SELECT id, apartment_id, filing_id, reversed_at, reversed_by FROM stay_fee_adjustment ORDER BY id`),
		"stay_fee_filing":     rows(t, pool, `SELECT id, apartment_id, period_key, superseded_at, sent_at, paid_at FROM stay_fee_filing ORDER BY id`),
		"apartment":           rows(t, pool, `SELECT id, `+fee+` FROM apartment ORDER BY id`),
	}
	rs, err := pool.Query(context.Background(),
		`SELECT id, fee_host_decision, fee_host_reason, fee_host_reason_enc, fee_host_reason_reference, updated_at FROM guest ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	defer rs.Close()
	guests := []any{}
	for rs.Next() {
		var id int64
		var decision, plain, enc, reference, updated *string
		if err := rs.Scan(&id, &decision, &plain, &enc, &reference, &updated); err != nil {
			t.Fatal(err)
		}
		reason := plain
		encSet := enc != nil && *enc != ""
		if encSet {
			if plain != nil {
				t.Fatalf("guest %d keeps a plaintext reason next to its ciphertext", id)
			}
			out, err := keys.Decrypt(*enc, 0, time.Now())
			if err != nil {
				t.Fatalf("guest %d reason does not decrypt", id)
			}
			text := string(out)
			reason = &text
		}
		guests = append(guests, map[string]any{
			"id": id, "decision": decision, "reason": reason, "reason_plain_column": nil,
			"reason_enc_set": encSet, "reference": reference, "updated_at": updated,
		})
	}
	if err := rs.Err(); err != nil {
		t.Fatal(err)
	}
	snap["guest"] = guests
	return snap
}

// normal round-trips v through JSON so Go and golden values compare.
func normal(t *testing.T, v any) any {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var out any
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	if err := dec.Decode(&out); err != nil {
		t.Fatal(err)
	}
	return out
}

func csrfPair(t *testing.T, at time.Time) (*http.Cookie, string) {
	t.Helper()
	cookie := "stayfees-csrf-cookie"
	sum := sha256.Sum256([]byte(cookie))
	token, err := secure.NewTimedSerializer(goldenSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, at)
	if err != nil {
		t.Fatal(err)
	}
	return &http.Cookie{Name: "ubyhost_csrf", Value: cookie}, token
}

// sessionFor is auth.issue_session for the golden accounts.
func sessionFor(who string, at time.Time) string {
	payload := map[string]any{"sv": 1, "iat": at.Unix()}
	switch who {
	case "host1":
		payload["uid"] = 1
	case "host2":
		payload["uid"] = 2
	case "admin_imp":
		payload["uid"] = 3
		payload["as"] = 1
		payload["ast"] = at.Unix()
	}
	return session.Sign(goldenSecret, payload, at)
}

func newMux(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) *http.ServeMux {
	mux := http.NewServeMux()
	for _, r := range Routes(pool, getenv, now) {
		mux.Handle(r.Pattern, r.Handler)
	}
	return mux
}

func request(t *testing.T, c goldenCase, at time.Time) *http.Request {
	t.Helper()
	form := url.Values{}
	for k, v := range c.Form {
		form.Set(k, v)
	}
	var req *http.Request
	if c.Method == http.MethodPost {
		req = httptest.NewRequest(c.Method, c.Path, strings.NewReader(form.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		ck, token := csrfPair(t, at)
		req.AddCookie(ck)
		req.Header.Set("X-CSRF-Token", token)
	} else {
		req = httptest.NewRequest(c.Method, c.Path, nil)
	}
	if c.Who != nil {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor(*c.Who, at)})
	}
	if c.Lang != nil {
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: *c.Lang})
	}
	return req
}

func str(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// TestActionsMatchPython replays every golden case against the Go handlers on
// PostgreSQL and compares status, Location, CSV headers and body, and every
// row each request changed.
func TestActionsMatchPython(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g)
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	env := map[string]string{"UBYHOST_SECRET_KEY": goldenSecret}
	getenv := func(k string) string { return env[k] }
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		t.Fatal(err)
	}
	mux := newMux(pool, getenv, func() time.Time { return at })

	previous := normal(t, snapshot(t, pool, keys)).(map[string]any)
	want := normal(t, g.Initial).(map[string]any)
	for table := range want {
		if !reflect.DeepEqual(previous[table], want[table]) {
			t.Fatalf("seeded %s differs from the golden initial snapshot:\n go: %v\nwant: %v", table, previous[table], want[table])
		}
	}
	// Python answers 500 for a property that is not the host's on /paid; Go
	// redirects like the sibling routes (deviation recorded in brief 1330).
	var noSuchApartment string
	for _, c := range g.Cases {
		if c.Name == "csv foreign apartment" {
			noSuchApartment = str(c.Location)
		}
	}
	if noSuchApartment == "" {
		t.Fatal("golden file has no csv foreign apartment case")
	}
	saved := identityVisible
	t.Cleanup(func() { identityVisible = saved })
	for _, c := range g.Cases {
		identityVisible = saved
		if c.IdentityHidden {
			identityVisible = func(*session.Host) bool { return false }
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, request(t, c, at))
		wantStatus, wantLocation := c.Status, str(c.Location)
		if strings.HasSuffix(c.Name, "(python 500)") {
			wantStatus, wantLocation = http.StatusSeeOther, noSuchApartment
		}
		if rec.Code != wantStatus {
			t.Errorf("%s: status %d, want %d (%s)", c.Name, rec.Code, wantStatus, rec.Body.String())
			continue
		}
		if got := rec.Header().Get("Location"); got != wantLocation {
			t.Errorf("%s: Location\n got %q\nwant %q", c.Name, got, wantLocation)
		}
		if wantStatus == http.StatusOK {
			for _, h := range []struct {
				name string
				want *string
			}{{"Content-Type", c.ContentType}, {"Content-Disposition", c.ContentDisposition}, {"Cache-Control", c.CacheControl}} {
				if got := rec.Header().Get(h.name); got != str(h.want) {
					t.Errorf("%s: %s %q, want %q", c.Name, h.name, got, str(h.want))
				}
			}
			if got := rec.Body.String(); got != str(c.Body) {
				t.Errorf("%s: body %q, want %q", c.Name, got, str(c.Body))
			}
		}
		current := normal(t, snapshot(t, pool, keys)).(map[string]any)
		changed := map[string]any{}
		for table, now := range current {
			if !reflect.DeepEqual(now, previous[table]) {
				changed[table] = now
			}
		}
		if now, ok := changed["audit"]; ok {
			before, _ := previous["audit"].([]any)
			changed["audit_new"] = now.([]any)[len(before):]
			delete(changed, "audit")
		}
		previous = current
		if want := normal(t, c.Changed); !reflect.DeepEqual(normal(t, changed), want) {
			t.Errorf("%s: changed rows\n got %v\nwant %v", c.Name, normal(t, changed), want)
		}
	}
}

// TestCSRFRequired: a POST without a token from another site is refused
// before any row changes (protect_host_post).
func TestCSRFRequired(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g)
	at, _ := time.Parse(time.RFC3339, g.Now)
	env := map[string]string{"UBYHOST_SECRET_KEY": goldenSecret}
	getenv := func(k string) string { return env[k] }
	mux := newMux(pool, getenv, func() time.Time { return at })
	req := httptest.NewRequest(http.MethodPost, "/stay-fees/12/filings/1/sent", strings.NewReader("month=2026-10"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Origin", "https://evil.example")
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor("host1", at)})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusForbidden {
		t.Fatalf("status %d, want 403", rec.Code)
	}
	var sent *string
	if err := pool.QueryRow(context.Background(), `SELECT sent_at FROM stay_fee_filing WHERE id = 1`).Scan(&sent); err != nil {
		t.Fatal(err)
	}
	if sent != nil {
		t.Fatal("a refused POST changed the filing")
	}
}

// TestRoutesNeedNoPool: Routes builds with a nil pool, as the registry requires.
func TestRoutesNeedNoPool(t *testing.T) {
	routes := Routes(nil, func(string) string { return "" }, time.Now)
	if len(routes) != 8 {
		t.Fatalf("%d routes, want 8", len(routes))
	}
	mux := http.NewServeMux()
	for _, r := range routes {
		if r.Pattern == "GET /" || r.Handler == nil {
			t.Fatalf("bad route %q", r.Pattern)
		}
		mux.Handle(r.Pattern, r.Handler)
	}
}
