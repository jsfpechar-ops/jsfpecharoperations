package stayfees

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"mime/multipart"
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

// acceptedVersion is the legal version the tests run with: goldenEnv sets
// UBYHOST_TERMS_VERSION, UBYHOST_PRIVACY_VERSION and UBYHOST_DPA_VERSION, which
// session.AcceptancePending reads, and seed stores it as accepted. The test so
// does not depend on the session package's unexported default.
const acceptedVersion = "test-accepted"

// goldenEnv is the environment every test runs with.
func goldenEnv() func(string) string {
	env := map[string]string{
		"UBYHOST_SECRET_KEY":      goldenSecret,
		"UBYHOST_TERMS_VERSION":   acceptedVersion,
		"UBYHOST_PRIVACY_VERSION": acceptedVersion,
		"UBYHOST_DPA_VERSION":     acceptedVersion,
	}
	return func(k string) string { return env[k] }
}

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
	// account has accepted the version goldenEnv names.
	for _, uid := range []int{1, 2, 3} {
		for _, doc := range []string{"terms", "privacy", "dpa"} {
			if _, err := pool.Exec(ctx,
				`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, '2026-01-01', 'clickwrap')`,
				uid, doc, acceptedVersion); err != nil {
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
	getenv := goldenEnv()
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
	getenv := goldenEnv()
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

// goldenCaseNamed returns the golden case with this name.
func goldenCaseNamed(t *testing.T, g golden, name string) goldenCase {
	t.Helper()
	for _, c := range g.Cases {
		if c.Name == name {
			return c
		}
	}
	t.Fatalf("golden file has no case %q", name)
	return goldenCase{}
}

// TestCSVHeadNotAllowed: FastAPI lists GET only, so HEAD is a 405 with
// Allow: GET before any dependency runs. The nil pool proves no DB access.
func TestCSVHeadNotAllowed(t *testing.T) {
	at := time.Date(2026, 11, 13, 9, 0, 0, 0, time.UTC)
	mux := newMux(nil, goldenEnv(), func() time.Time { return at })
	req := httptest.NewRequest(http.MethodHead, "/stay-fees/12/csv?month=2026-10", nil)
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor("host1", at)})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("status %d, want 405", rec.Code)
	}
	if got := rec.Header().Get("Allow"); got != "GET" {
		t.Errorf("Allow %q, want GET", got)
	}
	if got := rec.Header().Get("Content-Type"); got != "application/json" {
		t.Errorf("Content-Type %q, want application/json", got)
	}
	if got := rec.Body.String(); got != `{"detail":"Method Not Allowed"}` {
		t.Errorf("body %q", got)
	}
}

// TestOverflowIDNotFound: an all-digit path id outside int64 parses in
// FastAPI and Postgres finds no row for it, so each route takes its not-found
// branch. Every case replays a golden not-found case with the id replaced and
// expects the golden answer (redirect texts carry str(int) of the id). A
// non-integer id stays a 422.
func TestOverflowIDNotFound(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g)
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	getenv := goldenEnv()
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		t.Fatal(err)
	}
	mux := newMux(pool, getenv, func() time.Time { return at })
	noSuchApartment := str(goldenCaseNamed(t, g, "csv foreign apartment").Location)
	const big = "99999999999999999999"
	cases := []struct {
		golden             string
		pathOld, pathNew   string
		whereOld, whereNew string
	}{
		{"undo foreign apartment", "/20/", "/" + big + "/", "", ""},
		{"undo missing row", "/999/", "/" + big + "/", "", ""},
		{"scope missing apartment", "/999/", "/" + big + "/", "", ""},
		{"copy foreign target", "/20/", "/" + big + "/", "", ""},
		{"paid missing apartment (python 500)", "/999/", "/" + big + "/", "", ""},
		{"sent foreign apartment", "/20/", "/" + big + "/", "", ""},
		{"sent filing of another apartment", "/filings/1/", "/filings/" + big + "/", "", ""},
		{"paid filing foreign apartment", "/20/", "/-" + big + "/", "", ""},
		{"paid filing wrong month", "/filings/3/", "/filings/" + big + "/", "", ""},
		{"csv missing apartment", "/999/", "/" + big + "/", "", ""},
		{"csv future month", "/12/", "/+000" + big + "/", "/12/", "/" + big + "/"},
		{"csv identity hidden", "/12/", "/" + big + "/", "/12?", "/" + big + "?"},
	}
	saved := identityVisible
	t.Cleanup(func() { identityVisible = saved })
	before := normal(t, snapshot(t, pool, keys))
	for _, tc := range cases {
		c := goldenCaseNamed(t, g, tc.golden)
		c.Path = strings.Replace(c.Path, tc.pathOld, tc.pathNew, 1)
		wantStatus, wantLocation := c.Status, str(c.Location)
		if strings.HasSuffix(c.Name, "(python 500)") {
			wantStatus, wantLocation = http.StatusSeeOther, noSuchApartment
		}
		if tc.whereOld != "" {
			wantLocation = strings.Replace(wantLocation, tc.whereOld, tc.whereNew, 1)
		}
		identityVisible = saved
		if c.IdentityHidden {
			identityVisible = func(*session.Host) bool { return false }
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, request(t, c, at))
		if rec.Code != wantStatus || rec.Header().Get("Location") != wantLocation {
			t.Errorf("%s: %d %q, want %d %q (%s)", c.Path, rec.Code, rec.Header().Get("Location"), wantStatus, wantLocation, rec.Body.String())
		}
	}
	identityVisible = saved
	for _, path := range []string{"/stay-fees/1x/csv", "/stay-fees/%D9%A3/csv", "/stay-fees/12/filings/1.5/sent"} {
		c := goldenCase{Method: http.MethodGet, Path: path, Who: &[]string{"host1"}[0]}
		if strings.HasSuffix(path, "/sent") {
			c.Method = http.MethodPost
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, request(t, c, at))
		if rec.Code != http.StatusUnprocessableEntity {
			t.Errorf("%s: status %d, want 422", path, rec.Code)
		}
	}
	if after := normal(t, snapshot(t, pool, keys)); !reflect.DeepEqual(after, before) {
		t.Errorf("a not-found request changed rows:\n got %v\nwant %v", after, before)
	}
}

// TestMultipartForm: request.form() reads multipart/form-data too. The golden
// "scope ok" case, posted as multipart with the CSRF token in the _csrf field
// (no header), gives the same redirect and saves the ruling.
func TestMultipartForm(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g)
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	mux := newMux(pool, goldenEnv(), func() time.Time { return at })
	c := goldenCaseNamed(t, g, "scope ok")
	ck, token := csrfPair(t, at)
	var body strings.Builder
	mw := multipart.NewWriter(&body)
	if err := mw.WriteField("_csrf", token); err != nil {
		t.Fatal(err)
	}
	for _, k := range []string{"month", "reference", "rule"} {
		if err := mw.WriteField(k, c.Form[k]); err != nil {
			t.Fatal(err)
		}
	}
	if err := mw.Close(); err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, c.Path, strings.NewReader(body.String()))
	req.Header.Set("Content-Type", mw.FormDataContentType())
	req.AddCookie(ck)
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor(*c.Who, at)})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != c.Status || rec.Header().Get("Location") != str(c.Location) {
		t.Fatalf("%d %q, want %d %q (%s)", rec.Code, rec.Header().Get("Location"), c.Status, str(c.Location), rec.Body.String())
	}
	var rule, reference string
	if err := pool.QueryRow(context.Background(),
		`SELECT stay_fee_scope_rule, stay_fee_scope_reference FROM apartment WHERE id = 12`).Scan(&rule, &reference); err != nil {
		t.Fatal(err)
	}
	if rule != c.Form["rule"] || reference != c.Form["reference"] {
		t.Errorf("saved %q %q, want %q %q", rule, reference, c.Form["rule"], c.Form["reference"])
	}
}
